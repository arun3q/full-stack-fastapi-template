from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import create_engine, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.models import ROLE_ADMIN, User, UserCreate

# Synchronous engine, used for Alembic migrations and CLI/pre-start scripts.
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=settings.POSTGRES_POOL_PRE_PING,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
)

# Asynchronous engine, used by the application for request/response handling.
# The same psycopg driver is used in async mode, so no extra dependency is needed.
async_engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=settings.POSTGRES_POOL_PRE_PING,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
)

async_session_factory = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Optional read-replica engine (falls back to the primary when not configured)
_read_engine = None
if settings.READ_REPLICA_URL:
    _read_engine = create_async_engine(
        settings.READ_REPLICA_URL,
        pool_pre_ping=settings.POSTGRES_POOL_PRE_PING,
        pool_size=settings.POSTGRES_POOL_SIZE,
        max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
    )
_read_session_factory = async_sessionmaker(
    _read_engine if _read_engine is not None else async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """Dependency that yields an async DB session for the duration of a request."""
    async with async_session_factory() as session:
        yield session


async def get_read_session() -> AsyncGenerator[AsyncSession]:
    """Dependency that yields a read-only DB session (read replica when set)."""
    async with _read_session_factory() as session:
        yield session


async def set_tenant_context(
    session: AsyncSession, *, organization_id: Any, is_admin: bool
) -> None:
    """Set the Postgres RLS GUCs for the current request transaction.

    Only used when ``ENABLE_RLS`` is on (see ``ops.md`` for the policies).
    """
    if not settings.ENABLE_RLS:
        return
    connection = await session.connection()
    await connection.execute(
        text("SELECT set_config('app.current_org_id', :org, true)"),
        {"org": str(organization_id) if organization_id is not None else ""},
    )
    await connection.execute(
        text("SELECT set_config('app.is_admin', :admin, true)"),
        {"admin": "true" if is_admin else "false"},
    )


async def init_db(session: AsyncSession) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = (
        await session.exec(select(User).where(User.email == settings.FIRST_SUPERUSER))
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            role=ROLE_ADMIN,
            is_verified=True,
        )
        user = await crud.create_user(session=session, user_create=user_in)
