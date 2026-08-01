"""Billing hardening: one-active-sub per org, PaymentEvent.subscription_id, larger raw

Revision ID: f4a6c8d0e2f1
Revises: e3f5a7b9c1d2
Create Date: 2026-08-01 11:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f4a6c8d0e2f1'
down_revision = 'e3f5a7b9c1d2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('paymentevent', sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_paymentevent_subscription_id', 'paymentevent', 'subscription', ['subscription_id'], ['id'], ondelete='SET NULL')

    # Exactly one active/trialing/past_due subscription per organization
    op.execute(
        "CREATE UNIQUE INDEX uq_subscription_one_active_per_org "
        "ON subscription (organization_id) "
        "WHERE status IN ('active', 'trialing', 'past_due') AND organization_id IS NOT NULL;"
    )

    op.alter_column('paymentevent', 'raw', existing_type=sa.String(length=10000), type_=sa.String(length=30000), existing_nullable=False, existing_server_default='{}')


def downgrade():
    op.alter_column('paymentevent', 'raw', existing_type=sa.String(length=30000), type_=sa.String(length=10000), existing_nullable=False, existing_server_default='{}')
    op.execute("DROP INDEX IF EXISTS uq_subscription_one_active_per_org;")
    op.drop_constraint('fk_paymentevent_subscription_id', 'paymentevent', type_='foreignkey')
    op.drop_column('paymentevent', 'subscription_id')
