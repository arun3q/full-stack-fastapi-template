from fastapi import APIRouter

from app.api.routes import (
    admin,
    ai,
    api_keys,
    auth,
    files,
    items,
    login,
    notifications,
    organizations,
    payments,
    private,
    public,
    sessions,
    totp,
    users,
    utils,
    webhooks,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
# sessions/totp must be registered before auth's catch-all /{provider}
api_router.include_router(sessions.router)
api_router.include_router(totp.router)
api_router.include_router(auth.router)
api_router.include_router(public.router)
api_router.include_router(organizations.router)
api_router.include_router(payments.router)
api_router.include_router(ai.router)
api_router.include_router(webhooks.router)
api_router.include_router(api_keys.router)
api_router.include_router(notifications.router)
api_router.include_router(files.router)
api_router.include_router(admin.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
