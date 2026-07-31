import uuid
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

ROLE_USER = "user"
ROLE_STAFF = "staff"
ROLE_ADMIN = "admin"

# Organization member roles (per-tenant)
ORG_ROLE_OWNER = "owner"
ORG_ROLE_ADMIN = "admin"
ORG_ROLE_MEMBER = "member"
ORG_ROLE_VIEWER = "viewer"

# Invitation statuses
INVITE_PENDING = "pending"
INVITE_ACCEPTED = "accepted"
INVITE_DECLINED = "declined"
INVITE_CANCELED = "canceled"
INVITE_EXPIRED = "expired"


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    role: str = Field(default=ROLE_USER, max_length=30)
    is_verified: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    role: str | None = Field(default=None, max_length=30)
    is_verified: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Nullable for users that authenticate exclusively via a social provider
    hashed_password: str | None = Field(default=None, max_length=255)
    totp_secret: str | None = Field(default=None, max_length=64)
    totp_enabled: bool = False
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)
    oauth_accounts: list[OAuthAccount] = Relationship(
        back_populates="user", cascade_delete=True
    )
    subscriptions: list[Subscription] = Relationship(back_populates="user")
    memberships: list[OrganizationMember] = Relationship(
        back_populates="user", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
    next_cursor: str | None = None


class UserAccess(SQLModel):
    role: str
    is_superuser: bool
    is_verified: bool
    plan: PlanPublic | None = None
    features: list[str]


# Organizations / multi-tenancy
class Organization(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    is_active: bool = True
    slug: str = Field(unique=True, index=True, max_length=100)
    # JSON string, e.g. {"accent": "teal", "logo_url": "https://..."}
    branding: str | None = Field(default=None, max_length=2000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    members: list[OrganizationMember] = Relationship(
        back_populates="organization", cascade_delete=True
    )
    invites: list[OrganizationInvite] = Relationship(
        back_populates="organization", cascade_delete=True
    )
    items: list[Item] = Relationship(back_populates="organization")
    subscriptions: list[Subscription] = Relationship(back_populates="organization")


class OrganizationCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    branding: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class OrganizationPublic(SQLModel):
    id: uuid.UUID
    name: str
    slug: str
    branding: str | None = None
    created_at: datetime | None = None


class OrganizationsPublic(SQLModel):
    data: list[OrganizationPublic]
    count: int


class MyOrganizationPublic(OrganizationPublic):
    role: str


class OrganizationMember(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_id: uuid.UUID = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    role: str = Field(default=ORG_ROLE_MEMBER, max_length=30)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    organization: Organization | None = Relationship(back_populates="members")
    user: User | None = Relationship(back_populates="memberships")


class OrganizationMemberPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str | None = None
    full_name: str | None = None
    role: str
    created_at: datetime | None = None


class OrganizationMembersPublic(SQLModel):
    data: list[OrganizationMemberPublic]
    count: int


class OrganizationInvite(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_id: uuid.UUID = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    email: EmailStr = Field(index=True, max_length=255)
    role: str = Field(default=ORG_ROLE_MEMBER, max_length=30)
    token: str = Field(unique=True, index=True, max_length=255)
    invited_by: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    status: str = Field(default=INVITE_PENDING, max_length=20)
    expires_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    organization: Organization | None = Relationship(back_populates="invites")


class OrganizationInviteCreate(SQLModel):
    email: EmailStr
    role: str = Field(default=ORG_ROLE_MEMBER, max_length=30)


class OrganizationInvitePublic(SQLModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    role: str
    status: str
    created_at: datetime | None = None


class OrganizationInvitesPublic(SQLModel):
    data: list[OrganizationInvitePublic]
    count: int


class PublicConfig(SQLModel):
    project_name: str
    support_email: str | None = None


class VerifyEmailRequest(SQLModel):
    token: str


class ResendVerificationEmail(SQLModel):
    email: EmailStr


class OAuthAccount(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_account_provider_account"
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    provider: str = Field(max_length=50, index=True)
    provider_account_id: str = Field(max_length=255)
    provider_email: str | None = Field(default=None, max_length=255)
    access_token: str | None = Field(default=None, max_length=2048)
    refresh_token: str | None = Field(default=None, max_length=2048)
    expires_at: int | None = None
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    user: User | None = Relationship(back_populates="oauth_accounts")


class OAuthAccountPublic(SQLModel):
    id: uuid.UUID
    provider: str
    provider_email: str | None = None


class Plan(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    slug: str = Field(unique=True, index=True, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    amount_cents: int
    currency: str = Field(default="usd", max_length=10)
    billing_interval: str = Field(default="month", max_length=20)
    provider_plan_id: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    trial_days: int = 0
    features: str | None = Field(default=None, max_length=2000)
    # JSON string, e.g. {"max_items": 5, "max_seats": 1, "ai_calls": 50}
    quotas: str | None = Field(default=None, max_length=2000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    subscriptions: list[Subscription] = Relationship(back_populates="plan")


class PlanCreate(SQLModel):
    name: str = Field(max_length=100)
    slug: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    amount_cents: int
    currency: str = Field(default="usd", max_length=10)
    billing_interval: str = Field(default="month", max_length=20)
    provider_plan_id: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    features: str | None = Field(default=None, max_length=2000)
    quotas: str | None = Field(default=None, max_length=2000)


class PlanPublic(SQLModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    amount_cents: int
    currency: str
    billing_interval: str
    is_active: bool
    features: str | None = None
    quotas: str | None = None


class PlansPublic(SQLModel):
    data: list[PlanPublic]
    count: int


class Subscription(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_id: uuid.UUID | None = Field(
        default=None, foreign_key="organization.id", ondelete="CASCADE"
    )
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="CASCADE"
    )
    plan_id: uuid.UUID | None = Field(
        default=None, foreign_key="plan.id", ondelete="RESTRICT"
    )
    provider: str = Field(max_length=20, index=True)
    provider_subscription_id: str | None = Field(
        default=None, unique=True, index=True, max_length=255
    )
    provider_customer_id: str | None = Field(default=None, max_length=255)
    status: str = Field(default="incomplete", max_length=30, index=True)
    quantity: int = 1
    current_period_start: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    current_period_end: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    cancel_at_period_end: bool = False
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    user: User | None = Relationship(back_populates="subscriptions")
    organization: Organization | None = Relationship(back_populates="subscriptions")
    plan: Plan | None = Relationship(back_populates="subscriptions")


class SubscriptionPublic(SQLModel):
    id: uuid.UUID
    plan: PlanPublic | None = None
    provider: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class PaymentEvent(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_id: uuid.UUID | None = Field(
        default=None, foreign_key="organization.id", ondelete="SET NULL"
    )
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    provider: str = Field(max_length=20, index=True)
    provider_event_id: str = Field(unique=True, index=True, max_length=255)
    event_type: str = Field(max_length=100, index=True)
    amount_cents: int | None = None
    currency: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, max_length=50)
    raw: str = Field(default="{}", max_length=10000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class UsageEvent(SQLModel, table=True):
    """A single metered usage record for an organization and meter."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_id: uuid.UUID = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    meter: str = Field(max_length=50, index=True)
    amount: int = 1
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class PaymentEventPublic(SQLModel):
    id: uuid.UUID
    provider: str
    event_type: str
    amount_cents: int | None = None
    currency: str | None = None
    status: str | None = None
    created_at: datetime | None = None


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    organization_id: uuid.UUID | None = Field(
        default=None, foreign_key="organization.id", ondelete="CASCADE"
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")
    organization: Organization | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int
    next_cursor: str | None = None


# AI chat
class ChatMessage(SQLModel):
    role: str = Field(max_length=20)
    content: str


class ChatRequest(SQLModel):
    messages: list[ChatMessage]
    system_prompt: str | None = Field(default=None, max_length=4000)


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# Auth sessions (refresh tokens) ---------------------------------------------
class Session(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    refresh_token_hash: str = Field(unique=True, index=True, max_length=255)
    ip_address: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, max_length=512)
    expires_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class SessionPublic(SQLModel):
    id: uuid.UUID
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class SessionsPublic(SQLModel):
    data: list[SessionPublic]
    count: int


class RefreshRequest(SQLModel):
    refresh_token: str


# Audit log ------------------------------------------------------------------
class AuditLog(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    organization_id: uuid.UUID | None = Field(
        default=None, foreign_key="organization.id", ondelete="SET NULL"
    )
    action: str = Field(index=True, max_length=100)
    entity_type: str | None = Field(default=None, max_length=100)
    entity_id: str | None = Field(default=None, max_length=100)
    ip_address: str | None = Field(default=None, max_length=64)
    detail: str | None = Field(default=None, max_length=4000)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AuditLogPublic(SQLModel):
    id: uuid.UUID
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    ip_address: str | None = None
    detail: str | None = None
    created_at: datetime | None = None


class AuditLogsPublic(SQLModel):
    data: list[AuditLogPublic]
    count: int
    next_cursor: str | None = None


# Outbound webhooks ----------------------------------------------------------
class Webhook(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_id: uuid.UUID = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    url: str = Field(max_length=2048)
    secret: str = Field(max_length=255)
    events: str = Field(default="[]", max_length=2000)
    is_active: bool = True
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class WebhookCreate(SQLModel):
    url: str = Field(min_length=1, max_length=2048)
    secret: str = Field(default="", min_length=0, max_length=255)
    events: list[str] = Field(default_factory=list)


class WebhookUpdate(SQLModel):
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    is_active: bool | None = None
    events: list[str] | None = None


class WebhookPublic(SQLModel):
    id: uuid.UUID
    url: str
    events: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime | None = None


class WebhooksPublic(SQLModel):
    data: list[WebhookPublic]
    count: int


class WebhookDelivery(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    webhook_id: uuid.UUID = Field(
        foreign_key="webhook.id", nullable=False, ondelete="CASCADE"
    )
    event: str = Field(max_length=100)
    payload: str = Field(default="{}", max_length=10000)
    status: str = Field(default="pending", max_length=20)
    attempts: int = 0
    response_status: int | None = None
    response_body: str | None = Field(default=None, max_length=2000)
    next_retry_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class WebhookDeliveryPublic(SQLModel):
    id: uuid.UUID
    event: str
    status: str
    attempts: int
    response_status: int | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class WebhookDeliveriesPublic(SQLModel):
    data: list[WebhookDeliveryPublic]
    count: int


# API keys / service accounts ------------------------------------------------
class ApiKey(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    organization_id: uuid.UUID = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )
    name: str = Field(max_length=255)
    key_hash: str = Field(unique=True, index=True, max_length=255)
    scopes: str = Field(default="[]", max_length=2000)
    last_used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ApiKeyCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)


class ApiKeyPublic(SQLModel):
    id: uuid.UUID
    name: str
    scopes: list[str] = Field(default_factory=list)
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None


class ApiKeysPublic(SQLModel):
    data: list[ApiKeyPublic]
    count: int


class ApiKeyCreated(ApiKeyPublic):
    key: str


# Notifications --------------------------------------------------------------
class Notification(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    type: str = Field(default="info", max_length=50)
    title: str = Field(max_length=255)
    body: str | None = Field(default=None, max_length=2000)
    read_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class NotificationPublic(SQLModel):
    id: uuid.UUID
    type: str
    title: str
    body: str | None = None
    read_at: datetime | None = None
    created_at: datetime | None = None


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int


# TOTP 2FA -------------------------------------------------------------------
class TotpSetupRequest(SQLModel):
    password: str


class TotpEnableRequest(SQLModel):
    password: str
    code: str


class TotpDisableRequest(SQLModel):
    code: str


class TotpSetupResponse(SQLModel):
    secret: str
    otpauth_url: str


class LoginTotpRequest(SQLModel):
    totp_code: str


# Platform config helpers ----------------------------------------------------
class MetricsResponse(SQLModel):
    message: str
