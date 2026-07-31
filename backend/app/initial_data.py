import asyncio
import json
import logging
from typing import Any

from sqlmodel import select

from app.core.db import async_session_factory, init_db
from app.models import Plan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "name": "Free",
        "slug": "free",
        "description": "Get started with core features, no payment required.",
        "amount_cents": 0,
        "currency": "usd",
        "billing_interval": "month",
        "features": json.dumps(["1 project", "Community support"]),
    },
    {
        "name": "Pro",
        "slug": "pro",
        "description": "For individuals and small teams.",
        "amount_cents": 1999,
        "currency": "usd",
        "billing_interval": "month",
        "features": json.dumps(
            ["Unlimited projects", "Priority email support", "Advanced analytics"]
        ),
    },
    {
        "name": "Business",
        "slug": "business",
        "description": "For growing teams that need more power.",
        "amount_cents": 4999,
        "currency": "usd",
        "billing_interval": "month",
        "features": json.dumps(
            ["Everything in Pro", "Team seats (5)", "SSO & audit logs", "API access"]
        ),
    },
    {
        "name": "Enterprise",
        "slug": "enterprise",
        "description": "Custom plans and dedicated support.",
        "amount_cents": 9999,
        "currency": "usd",
        "billing_interval": "month",
        "features": json.dumps(
            [
                "Everything in Business",
                "Unlimited seats",
                "Custom SLAs",
                "Dedicated account manager",
            ]
        ),
    },
]


async def seed_plans() -> None:
    """Create default plans if none exist yet."""
    async with async_session_factory() as session:
        existing = (await session.exec(select(Plan))).first()
        if existing:
            return
        for plan_data in DEFAULT_PLANS:
            plan = Plan(**plan_data)
            session.add(plan)
        await session.commit()
        logger.info("Seeded %d default plans", len(DEFAULT_PLANS))


async def init() -> None:
    async with async_session_factory() as session:
        await init_db(session)
    await seed_plans()


async def main() -> None:
    logger.info("Creating initial data")
    await init()
    logger.info("Initial data created")


if __name__ == "__main__":
    asyncio.run(main())
