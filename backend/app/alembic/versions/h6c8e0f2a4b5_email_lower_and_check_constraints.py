"""Email case-insensitive uniqueness + CHECK constraints

Revision ID: h6c8e0f2a4b5
Revises: g5b7d9e1f3a4
Create Date: 2026-08-01 13:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = 'h6c8e0f2a4b5'
down_revision = 'g5b7d9e1f3a4'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE UNIQUE INDEX uq_user_email_lower ON \"user\" (lower(email));")

    op.execute(
        "ALTER TABLE organizationmember ADD CONSTRAINT ck_orgmember_role "
        "CHECK (role IN ('owner', 'admin', 'member', 'viewer'));"
    )
    op.execute(
        "ALTER TABLE subscription ADD CONSTRAINT ck_subscription_status "
        "CHECK (status IN ('incomplete', 'incomplete_expired', 'trialing', 'active', "
        "'past_due', 'unpaid', 'canceled', 'paused', 'failed'));"
    )
    op.execute("ALTER TABLE plan ADD CONSTRAINT ck_plan_amount_nonneg CHECK (amount_cents >= 0);")
    op.execute("ALTER TABLE subscription ADD CONSTRAINT ck_subscription_quantity_pos CHECK (quantity > 0);")
    op.execute("ALTER TABLE usageevent ADD CONSTRAINT ck_usageevent_amount_pos CHECK (amount > 0);")
    op.execute(
        "ALTER TABLE \"user\" ADD CONSTRAINT ck_user_role "
        "CHECK (role IN ('user', 'staff', 'admin'));"
    )


def downgrade():
    op.execute("ALTER TABLE \"user\" DROP CONSTRAINT IF EXISTS ck_user_role;")
    op.execute("ALTER TABLE usageevent DROP CONSTRAINT IF EXISTS ck_usageevent_amount_pos;")
    op.execute("ALTER TABLE subscription DROP CONSTRAINT IF EXISTS ck_subscription_quantity_pos;")
    op.execute("ALTER TABLE plan DROP CONSTRAINT IF EXISTS ck_plan_amount_nonneg;")
    op.execute("ALTER TABLE subscription DROP CONSTRAINT IF EXISTS ck_subscription_status;")
    op.execute("ALTER TABLE organizationmember DROP CONSTRAINT IF EXISTS ck_orgmember_role;")
    op.execute("DROP INDEX IF EXISTS uq_user_email_lower;")
