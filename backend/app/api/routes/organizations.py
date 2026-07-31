import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.core.access import billing_enabled, get_active_plan, plan_quota
from app.core.audit import record_audit
from app.core.config import settings
from app.core.jobs import send_email_background
from app.core.notifications import notify
from app.core.orgs import (
    ORG_ROLE_MEMBER,
    ORG_ROLE_OWNER,
    count_members,
    create_organization_invite,
    find_membership,
    has_permission,
    slugify,
)
from app.models import (
    INVITE_ACCEPTED,
    INVITE_EXPIRED,
    INVITE_PENDING,
    Message,
    MyOrganizationPublic,
    Organization,
    OrganizationCreate,
    OrganizationInvite,
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
    memberships = (
        await session.exec(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == current_user.id)
            .order_by(col(OrganizationMember.created_at).desc())
        )
    ).all()
    data: list[MyOrganizationPublic] = []
    for membership in memberships:
        org = await session.get(Organization, membership.organization_id)
        if org is None:
            continue
        data.append(
            MyOrganizationPublic.model_validate(org, update={"role": membership.role})
        )
    return {"data": data, "count": len(data)}


@router.post("/", response_model=OrganizationPublic)
async def create_organization(
    *, session: SessionDep, current_user: CurrentUser, body: OrganizationCreate
) -> Any:
    """Create a new organization; the creator becomes its owner."""
    base_slug = slugify(body.name)
    slug = base_slug
    counter = 1
    while (
        await session.exec(select(Organization).where(Organization.slug == slug))
    ).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    org = Organization(name=body.name, slug=slug)
    session.add(org)
    await session.flush()
    member = OrganizationMember(
        organization_id=org.id, user_id=current_user.id, role=ORG_ROLE_OWNER
    )
    session.add(member)
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
    org = await session.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/{organization_id}", response_model=OrganizationPublic)
async def update_organization(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    organization_id: uuid.UUID,
    body: OrganizationUpdate,
) -> Any:
    """Update an organization (admin+)."""
    await _require_permission(session, current_user, organization_id, "org:update")
    org = await session.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if body.name:
        org.name = body.name
    session.add(org)
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
    memberships = (
        await session.exec(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(col(OrganizationMember.created_at))
        )
    ).all()
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

    org = await session.get(Organization, organization_id)
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

    pending = (
        await session.exec(
            select(OrganizationInvite).where(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.email == body.email,
                OrganizationInvite.status == INVITE_PENDING,
            )
        )
    ).first()
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

    invite = await create_organization_invite(
        session,
        organization=org,
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
    invites = (
        await session.exec(
            select(OrganizationInvite)
            .where(OrganizationInvite.organization_id == organization_id)
            .order_by(col(OrganizationInvite.created_at).desc())
        )
    ).all()
    return {
        "data": [OrganizationInvitePublic.model_validate(i) for i in invites],
        "count": len(invites),
    }


@router.post("/invites/{token}/accept", response_model=Message)
async def accept_invite(
    session: SessionDep, current_user: CurrentUser, token: str
) -> Any:
    """Accept an invitation (must be logged in with the invited email)."""
    invite = (
        await session.exec(
            select(OrganizationInvite).where(OrganizationInvite.token == token)
        )
    ).first()
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

    member = OrganizationMember(
        organization_id=invite.organization_id,
        user_id=current_user.id,
        role=invite.role,
    )
    session.add(member)
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
async def update_member_role(
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
    member = (
        await session.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
    ).first()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    # Only the owner may promote/demote the owner role
    if member.role == ORG_ROLE_OWNER or role == ORG_ROLE_OWNER:
        await _require_permission(
            session, current_user, organization_id, "member:remove"
        )

    member.role = role
    session.add(member)
    await session.commit()
    await session.refresh(member)
    user = await session.get(User, member.user_id)
    public = OrganizationMemberPublic.model_validate(member)
    public.email = user.email if user else None
    public.full_name = user.full_name if user else None
    return public


@router.delete("/{organization_id}/members/{user_id}", response_model=Message)
async def remove_member(
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
    member = (
        await session.exec(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
    ).first()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == ORG_ROLE_OWNER:
        raise HTTPException(status_code=403, detail="Cannot remove the owner")
    await session.delete(member)
    await session.commit()
    return Message(message="Member removed")
