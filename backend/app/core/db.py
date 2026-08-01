from collections.abc import AsyncGenerator
from typing import Any
from weakref import WeakKeyDictionary

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session as SyncSession
from sqlmodel import create_engine, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.models import ROLE_ADMIN, User, UserCreate

_CONNECT_ARGS = {"connect_timeout": 10}

# Synchronous engine, used for Alembic migrations and CLI/pre-start scripts.
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=settings.POSTGRES_POOL_PRE_PING,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
    pool_recycle=600,
    connect_args=_CONNECT_ARGS,
)

# Asynchronous engine, used by the application for request/response handling.
# The same psycopg driver is used in async mode, so no extra dependency is needed.
async_engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=settings.POSTGRES_POOL_PRE_PING,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_timeout=settings.POSTGRES_POOL_TIMEOUT,
    pool_recycle=600,
    connect_args=_CONNECT_ARGS,
)


# Re-apply the tenant RLS GUC on every new transaction (after a commit the
# SET LOCAL is lost; under PgBouncer transaction pooling the next transaction
# may even run on a different pooled connection). No-op unless
# set_tenant_context stored a tenant on the session.
_tenant_guc: WeakKeyDictionary[Any, dict[str, str]] = WeakKeyDictionary()


@event.listens_for(SyncSession, "after_begin")
def _reapply_tenant_guc(
    session: SyncSession, _transaction: Any, connection: Any
) -> None:  # noqa: ARG001
    if not settings.ENABLE_RLS:
        return
    state = _tenant_guc.get(session)
    if not state:
        return
    connection.execute(
        text("SELECT set_config('app.current_org_id', :org, true)"),
        {"org": state["org"]},
    )
    connection.execute(
        text("SELECT set_config('app.is_admin', :admin, true)"),
        {"admin": state["admin"]},
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
        pool_recycle=600,
        connect_args=_CONNECT_ARGS,
    )
_read_session_factory = async_sessionmaker(
    _read_engine if _read_engine is not None else async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    # Enforce read-only transactions on read sessions so a mis-routed write fails
    exec_options={"postgresql_readonly": True},
)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    """Dependency that yields an async DB session for the duration of a request."""
    async with async_session_factory() as session:
        yield session


_read_engine_ok: bool | None = None
_read_engine_checked: float | None = None
_READ_PROBE_INTERVAL = 30.0


async def _read_replica_available() -> bool:
    """Circuit breaker: probe the replica at most every 30s."""
    import time

    global _read_engine_ok, _read_engine_checked
    now = time.monotonic()
    if _read_engine is None:
        return False
    if (
        _read_engine_checked is not None
        and now - _read_engine_checked < _READ_PROBE_INTERVAL
    ):
        return bool(_read_engine_ok)
    _read_engine_checked = now
    try:
        async with _read_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        _read_engine_ok = True
    except Exception:
        _read_engine_ok = False
    return bool(_read_engine_ok)


async def get_read_session() -> AsyncGenerator[AsyncSession]:
    """Dependency that yields a read-only DB session (read replica when set).

    Falls back to the primary engine when the replica is unavailable.
    """
    if await _read_replica_available():
        async with _read_session_factory() as session:
            yield session
    else:
        async with async_session_factory() as session:
            yield session


async def set_tenant_context(
    session: AsyncSession, *, organization_id: Any, is_admin: bool
) -> None:
    """Set the Postgres RLS GUCs for the current request transaction.

    Only used when ``ENABLE_RLS`` is on (see ``ops.md`` for the policies).
    """
    if not settings.ENABLE_RLS:
        return
    org_id = str(organization_id) if organization_id is not None else ""
    is_admin = "true" if is_admin else "false"
    _tenant_guc[session.sync_session] = {"org": org_id, "admin": is_admin}
    connection = await session.connection()
    await connection.execute(
        text("SELECT set_config('app.current_org_id', :org, true)"),
        {"org": org_id},
    )
    await connection.execute(
        text("SELECT set_config('app.is_admin', :admin, true)"),
        {"admin": is_admin},
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
