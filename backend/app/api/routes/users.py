import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from app import crud
from app.api.deps import (
    CurrentOrg,
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.access import get_active_plan, resolve_features
from app.core.audit import record_audit
from app.core.config import settings
from app.core.jobs import send_email_background
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    PlanPublic,
    ResendVerificationEmail,
    UpdatePassword,
    User,
    UserAccess,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
    VerifyEmailRequest,
)
from app.utils import (
    generate_new_account_email,
    generate_verify_email_data,
    generate_verify_email_token,
    verify_email_token,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
async def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = (await session.exec(count_statement)).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = (await session.exec(statement)).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
async def create_user(
    *, session: SessionDep, current_user: CurrentUser, user_in: UserCreate
) -> Any:
    """
    Create new user.
    """
    user = await crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = await crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email,
            username=user_in.email,
            password=user_in.password or "",
        )
        await send_email_background(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    await record_audit(
        session,
        action="user.create",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user.id),
        detail={"email": str(user.email)},
    )
    return user


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = await crud.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
async def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(
        body.current_password, current_user.hashed_password or ""
    )
    if not verified:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    await session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
async def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.get("/me/access", response_model=UserAccess)
async def read_user_access(
    session: SessionDep, current_user: CurrentUser, current_org: CurrentOrg
) -> Any:
    """
    Get the current user's role, plan and resolved feature flags.
    """
    plan = await get_active_plan(session, current_org.id)
    return UserAccess(
        role=current_user.role,
        is_superuser=current_user.is_superuser,
        is_verified=current_user.is_verified,
        plan=PlanPublic.model_validate(plan) if plan else None,
        features=resolve_features(user=current_user, plan=plan),
    )


@router.delete("/me", response_model=Message)
async def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    await session.delete(current_user)
    await session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
async def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = await crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = await crud.create_user(session=session, user_create=user_create)
    # Send an email verification link
    if settings.emails_enabled and user.email:
        token = generate_verify_email_token(email=str(user.email))
        email_data = generate_verify_email_data(email_to=str(user.email), token=token)
        await send_email_background(
            email_to=str(user.email),
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.post("/verify-email", response_model=Message)
async def verify_email(session: SessionDep, body: VerifyEmailRequest) -> Any:
    """
    Verify the current user's email address using a token.
    """
    email = verify_email_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    user = await crud.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return Message(message="Email already verified")
    user.is_verified = True
    session.add(user)
    await session.commit()
    return Message(message="Email verified successfully")


@router.post("/verify-email/resend", response_model=Message)
async def resend_verification_email(
    session: SessionDep, body: ResendVerificationEmail
) -> Any:
    """
    Resend the email verification link for a given address.
    """
    user = await crud.get_user_by_email(session=session, email=body.email)
    if user and not user.is_verified and settings.emails_enabled:
        token = generate_verify_email_token(email=str(user.email))
        email_data = generate_verify_email_data(email_to=str(user.email), token=token)
        await send_email_background(
            email_to=str(user.email),
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(message="If that email is registered, a verification email was sent")


@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = await session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
async def update_user(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = await session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = await crud.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = await crud.update_user(session=session, db_user=db_user, user_in=user_in)
    await record_audit(
        session,
        action="user.update",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user_id),
    )
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    await session.exec(statement)
    await record_audit(
        session,
        action="user.delete",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user_id),
        detail={"email": str(user.email)},
    )
    await session.delete(user)
    await session.commit()
    return Message(message="User deleted successfully")
