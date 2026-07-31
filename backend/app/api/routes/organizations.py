import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.core.access import billing_enabled, get_active_plan, plan_quota
from app.core.audit import record_audit
from app.core.config import settings
from app.core.jobs import send_email_background
from app.core.notifications import notify
from app.core.orgs import ORG_ROLE_MEMBER, ORG_ROLE_OWNER, has_permission
from app.crud.organizations import (
    add_member,
    count_members,
    create_invite,
    create_organization,
    find_membership,
    get_invite_by_token,
    get_organization,
    get_pending_invite,
    list_invites,
    list_members,
    list_user_memberships,
    remove_member,
    update_member_role,
    update_organization,
)
from app.models import (
    INVITE_ACCEPTED,
    INVITE_EXPIRED,
    INVITE_PENDING,
    Message,
    MyOrganizationPublic,
    OrganizationCreate,
    OrganizationInviteCreate,
    OrganizationInvitePublic,
    OrganizationInvitesPublic,
    OrganizationMember,
    OrganizationMemberPublic,
    OrganizationMembersPublic,
    OrganizationPublic,
    OrganizationUpdate,
    User,
)
from app.utils import generate_organization_invite_email

router = APIRouter(prefix="/organizations", tags=["organizations"])

FREE_PLAN_MAX_SEATS = 1


async def _get_membership(
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
) -> OrganizationMember:
    membership = await find_membership(
        session, organization_id=organization_id, user_id=current_user.id
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return membership


async def _require_permission(
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
    permission: str,
) -> OrganizationMember:
    membership = await _get_membership(session, current_user, organization_id)
    if not has_permission(membership.role, permission):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
    return membership


@router.get("/", response_model=dict[str, Any])
async def read_my_organizations(session: SessionDep, current_user: CurrentUser) -> Any:
    """List the organizations the current user belongs to."""
    memberships = await list_user_memberships(session, current_user.id)
    data: list[MyOrganizationPublic] = []
    for membership in memberships:
        org = await get_organization(session, membership.organization_id)
        if org is None:
            continue
        data.append(
            MyOrganizationPublic.model_validate(org, update={"role": membership.role})
        )
    return {"data": data, "count": len(data)}


@router.post("/", response_model=OrganizationPublic)
async def create_organization_route(
    *, session: SessionDep, current_user: CurrentUser, body: OrganizationCreate
) -> Any:
    """Create a new organization; the creator becomes its owner."""
    org = await create_organization(session, name=body.name, user=current_user)
    await record_audit(
        session,
        action="org.create",
        user_id=current_user.id,
        organization_id=org.id,
        entity_type="organization",
        entity_id=str(org.id),
        detail={"name": body.name},
    )
    await session.commit()
    await session.refresh(org)
    return org


@router.get("/{organization_id}", response_model=OrganizationPublic)
async def read_organization(
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
) -> Any:
    """Get organization details (members only)."""
    await _get_membership(session, current_user, organization_id)
    org = await get_organization(session, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/{organization_id}", response_model=OrganizationPublic)
async def update_organization_route(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
    body: OrganizationUpdate,
) -> Any:
    """Update an organization (admin+)."""
    await _require_permission(session, current_user, organization_id, "org:update")
    org = await get_organization(session, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if body.branding is not None:
        org.branding = body.branding
    org = await update_organization(session, org, name=body.name)
    await session.commit()
    await session.refresh(org)
    return org


@router.get("/{organization_id}/members", response_model=OrganizationMembersPublic)
async def read_members(
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
) -> Any:
    """List the members of an organization (members+)."""
    await _require_permission(session, current_user, organization_id, "org:view")
    memberships = await list_members(session, organization_id)
    data: list[OrganizationMemberPublic] = []
    for membership in memberships:
        user = await session.get(User, membership.user_id)
        public = OrganizationMemberPublic.model_validate(membership)
        public.email = user.email if user else None
        public.full_name = user.full_name if user else None
        data.append(public)
    return {"data": data, "count": len(data)}


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationInvitePublic,
)
async def invite_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
    body: OrganizationInviteCreate,
) -> Any:
    """Invite a user by email (admin+). Respects the plan's seat quota."""
    await _require_permission(session, current_user, organization_id, "member:invite")

    org = await get_organization(session, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing_user = (
        await session.exec(select(User).where(User.email == body.email))
    ).first()
    if existing_user:
        membership = await find_membership(
            session, organization_id=organization_id, user_id=existing_user.id
        )
        if membership:
            raise HTTPException(
                status_code=409, detail="User is already a member of this organization"
            )

    pending = await get_pending_invite(
        session, organization_id=organization_id, email=str(body.email)
    )
    if pending:
        raise HTTPException(status_code=409, detail="An invite is already pending")

    # Seat quota check (only when billing is configured)
    if billing_enabled():
        plan = await get_active_plan(session, organization_id)
        max_seats = (
            plan_quota(plan, "max_seats", default=0)
            if plan is not None
            else FREE_PLAN_MAX_SEATS
        )
        member_count = await count_members(session, organization_id)
        if max_seats > 0 and member_count >= max_seats:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Your plan allows {max_seats} seats. "
                    "Upgrade your plan to add more members."
                ),
            )

    invite = await create_invite(
        session,
        organization_id=org.id,
        email=str(body.email),
        role=body.role,
        invited_by=current_user,
    )
    await record_audit(
        session,
        action="org.invite",
        user_id=current_user.id,
        organization_id=org.id,
        entity_type="invite",
        entity_id=str(invite.id),
        detail={"email": str(body.email), "role": body.role},
    )
    await session.commit()

    invite_link = f"{settings.FRONTEND_HOST}/invite?token={invite.token}"
    email_data = generate_organization_invite_email(
        org_name=org.name,
        inviter_name=current_user.full_name or current_user.email,
        link=invite_link,
    )
    await send_email_background(
        email_to=str(body.email),
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return OrganizationInvitePublic.model_validate(invite)


@router.get("/{organization_id}/invites", response_model=OrganizationInvitesPublic)
async def read_invites(
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
) -> Any:
    """List pending invites for an organization (admin+)."""
    await _require_permission(session, current_user, organization_id, "member:invite")
    invites = await list_invites(session, organization_id)
    return {
        "data": [OrganizationInvitePublic.model_validate(i) for i in invites],
        "count": len(invites),
    }


@router.post("/invites/{token}/accept", response_model=Message)
async def accept_invite(
    session: SessionDep, current_user: CurrentUser, token: str
) -> Any:
    """Accept an invitation (must be logged in with the invited email)."""
    invite = await get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != INVITE_PENDING:
        raise HTTPException(status_code=400, detail="Invite is no longer pending")
    if invite.expires_at is not None and invite.expires_at < datetime.now(UTC):
        invite.status = INVITE_EXPIRED
        session.add(invite)
        await session.commit()
        raise HTTPException(status_code=400, detail="Invite has expired")
    if invite.email.lower() != current_user.email.lower():
        raise HTTPException(
            status_code=403,
            detail="This invite was sent to a different email address",
        )

    existing = await find_membership(
        session, organization_id=invite.organization_id, user_id=current_user.id
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Already a member of this organization"
        )

    await add_member(
        session,
        organization_id=invite.organization_id,
        user_id=current_user.id,
        role=invite.role,
    )
    invite.status = INVITE_ACCEPTED
    session.add(invite)
    # Notify whoever sent the invite
    if invite.invited_by is not None:
        await notify(
            session,
            user_id=invite.invited_by,
            type="team",
            title="Invitation accepted",
            body=f"{current_user.email} joined your organization",
        )
    await record_audit(
        session,
        action="org.member_joined",
        user_id=current_user.id,
        organization_id=invite.organization_id,
        entity_type="invite",
        entity_id=str(invite.id),
    )
    await session.commit()
    return Message(message="Invitation accepted")


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=OrganizationMemberPublic,
)
async def update_member_role_route(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> Any:
    """Change a member's role (admin+; owner management only by owners)."""
    await _require_permission(session, current_user, organization_id, "member:manage")
    if role not in (ORG_ROLE_OWNER, "admin", ORG_ROLE_MEMBER, "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    member = await update_member_role(
        session, organization_id=organization_id, user_id=user_id, role=role
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # Only the owner may promote/demote the owner role
    if member.role == ORG_ROLE_OWNER or role == ORG_ROLE_OWNER:
        await _require_permission(
            session, current_user, organization_id, "member:remove"
        )

    await session.commit()
    await session.refresh(member)
    user = await session.get(User, member.user_id)
    public = OrganizationMemberPublic.model_validate(member)
    public.email = user.email if user else None
    public.full_name = user.full_name if user else None
    return public


@router.delete("/{organization_id}/members/{user_id}", response_model=Message)
async def remove_member_route(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Any:
    """Remove a member (owner only)."""
    await _require_permission(session, current_user, organization_id, "member:remove")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    member = await remove_member(
        session, organization_id=organization_id, user_id=user_id
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == ORG_ROLE_OWNER:
        raise HTTPException(status_code=403, detail="Cannot remove the owner")
    await session.commit()
    return Message(message="Member removed")
