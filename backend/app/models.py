import uuid
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

ROLE_USER = "user"
ROLE_STAFF = "staff"
ROLE_ADMIN = "admin"


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
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)
    oauth_accounts: list[OAuthAccount] = Relationship(
        back_populates="user", cascade_delete=True
    )
    subscriptions: list[Subscription] = Relationship(back_populates="user")


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class UserAccess(SQLModel):
    role: str
    is_superuser: bool
    is_verified: bool
    plan: PlanPublic | None = None
    features: list[str]


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
    features: str | None = Field(default=None, max_length=2000)
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


class PlansPublic(SQLModel):
    data: list[PlanPublic]
    count: int


class Subscription(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
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
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


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


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
