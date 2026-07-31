from fastapi import APIRouter

from app.api.routes import (
    ai,
    auth,
    items,
    login,
    organizations,
    payments,
    private,
    public,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(auth.router)
api_router.include_router(public.router)
api_router.include_router(organizations.router)
api_router.include_router(payments.router)
api_router.include_router(ai.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
