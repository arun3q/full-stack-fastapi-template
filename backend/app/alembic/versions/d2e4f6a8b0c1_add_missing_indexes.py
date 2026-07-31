"""Add missing indexes on hot query columns

Revision ID: d2e4f6a8b0c1
Revises: c9d1e3a5f7b2
Create Date: 2026-07-31 21:30:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd2e4f6a8b0c1'
down_revision = 'c9d1e3a5f7b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_item_organization_id'), 'item', ['organization_id'], unique=False)
    op.create_index(op.f('ix_session_user_id'), 'session', ['user_id'], unique=False)
    op.create_index(op.f('ix_session_created_at'), 'session', ['created_at'], unique=False)
    op.create_index(op.f('ix_organizationmember_user_id'), 'organizationmember', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscription_organization_id'), 'subscription', ['organization_id'], unique=False)
    op.create_index(op.f('ix_subscription_plan_id'), 'subscription', ['plan_id'], unique=False)
    op.create_index(op.f('ix_webhookdelivery_webhook_id'), 'webhookdelivery', ['webhook_id'], unique=False)
    op.create_index(op.f('ix_webhookdelivery_status'), 'webhookdelivery', ['status'], unique=False)
    op.create_index(op.f('ix_webhookdelivery_next_retry_at'), 'webhookdelivery', ['next_retry_at'], unique=False)
    op.create_index(op.f('ix_organizationinvite_status'), 'organizationinvite', ['status'], unique=False)
    op.create_index(op.f('ix_organizationinvite_expires_at'), 'organizationinvite', ['expires_at'], unique=False)
    op.create_index(op.f('ix_user_created_at'), 'user', ['created_at'], unique=False)
    op.create_index(op.f('ix_organization_created_at'), 'organization', ['created_at'], unique=False)
    op.create_index(op.f('ix_auditlog_created_at'), 'auditlog', ['created_at'], unique=False)
    op.create_index(op.f('ix_usageevent_org_meter_created'), 'usageevent', ['organization_id', 'meter', 'created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_usageevent_org_meter_created'), table_name='usageevent')
    op.drop_index(op.f('ix_auditlog_created_at'), table_name='auditlog')
    op.drop_index(op.f('ix_organization_created_at'), table_name='organization')
    op.drop_index(op.f('ix_user_created_at'), table_name='user')
    op.drop_index(op.f('ix_organizationinvite_expires_at'), table_name='organizationinvite')
    op.drop_index(op.f('ix_organizationinvite_status'), table_name='organizationinvite')
    op.drop_index(op.f('ix_webhookdelivery_next_retry_at'), table_name='webhookdelivery')
    op.drop_index(op.f('ix_webhookdelivery_status'), table_name='webhookdelivery')
    op.drop_index(op.f('ix_webhookdelivery_webhook_id'), table_name='webhookdelivery')
    op.drop_index(op.f('ix_subscription_plan_id'), table_name='subscription')
    op.drop_index(op.f('ix_subscription_organization_id'), table_name='subscription')
    op.drop_index(op.f('ix_organizationmember_user_id'), table_name='organizationmember')
    op.drop_index(op.f('ix_session_created_at'), table_name='session')
    op.drop_index(op.f('ix_session_user_id'), table_name='session')
    op.drop_index(op.f('ix_item_organization_id'), table_name='item')
