"""Widen subscription status CHECK for Razorpay statuses

Revision ID: i7d9f1b3c5e6
Revises: h6c8e0f2a4b5
Create Date: 2026-08-01 15:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = 'i7d9f1b3c5e6'
down_revision = 'h6c8e0f2a4b5'
branch_labels = None
depends_on = None

_STATUSES = (
    "incomplete", "incomplete_expired", "trialing", "active", "past_due",
    "unpaid", "canceled", "paused", "failed", "completed", "halted", "pending",
)


def upgrade():
    op.execute(
        "ALTER TABLE subscription DROP CONSTRAINT IF EXISTS ck_subscription_status;"
    )
    op.execute(
        "ALTER TABLE subscription ADD CONSTRAINT ck_subscription_status "
        f"CHECK (status IN {_STATUSES});"
    )


def downgrade():
    op.execute(
        "ALTER TABLE subscription DROP CONSTRAINT IF EXISTS ck_subscription_status;"
    )
    op.execute(
        "ALTER TABLE subscription ADD CONSTRAINT ck_subscription_status "
        "CHECK (status IN ('incomplete', 'incomplete_expired', 'trialing', 'active', "
        "'past_due', 'unpaid', 'canceled', 'paused', 'failed'));"
    )
