"""Composite + missing indexes (notifications, hot filter/sort combos)

Revision ID: g5b7d9e1f3a4
Revises: f4a6c8d0e2f1
Create Date: 2026-08-01 12:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = 'g5b7d9e1f3a4'
down_revision = 'f4a6c8d0e2f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_notification_user_id'), 'notification', ['user_id'], unique=False)
    op.create_index(op.f('ix_notification_created_at'), 'notification', ['created_at'], unique=False)
    op.create_index(op.f('ix_item_org_created'), 'item', ['organization_id', sa.text('created_at DESC')], unique=False)
    op.create_index(op.f('ix_orgmember_org_user'), 'organizationmember', ['organization_id', 'user_id'], unique=False)
    op.create_index(op.f('ix_orginvite_org_status'), 'organizationinvite', ['organization_id', 'status'], unique=False)
    op.create_index(op.f('ix_subscription_org_status'), 'subscription', ['organization_id', 'status'], unique=False)
    op.create_index(op.f('ix_webhook_org_active'), 'webhook', ['organization_id', 'is_active'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_webhook_org_active'), table_name='webhook')
    op.drop_index(op.f('ix_subscription_org_status'), table_name='subscription')
    op.drop_index(op.f('ix_orginvite_org_status'), table_name='organizationinvite')
    op.drop_index(op.f('ix_orgmember_org_user'), table_name='organizationmember')
    op.drop_index(op.f('ix_item_org_created'), table_name='item')
    op.drop_index(op.f('ix_notification_created_at'), table_name='notification')
    op.drop_index(op.f('ix_notification_user_id'), table_name='notification')
