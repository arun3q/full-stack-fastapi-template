"""Add organization suspension + opt-in RLS policies

Revision ID: c9d1e3a5f7b2
Revises: b4c8f2a6d1e3
Create Date: 2026-07-31 21:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c9d1e3a5f7b2'
down_revision = 'b4c8f2a6d1e3'
branch_labels = None
depends_on = None

_TENANT_TABLES = ("item", "subscription", "organizationmember", "organizationinvite")


def upgrade():
    op.add_column(
        'organization',
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    # Optional Row-Level Security policies. They are permissive when the tenant
    # GUC is unset, so enabling them via migration is a safe no-op until
    # ENABLE_RLS is turned on (at which point the app sets app.current_org_id /
    # app.is_admin per request).
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              USING (
                COALESCE(NULLIF(current_setting('app.current_org_id', true), ''), '')
                  = ''
                OR current_setting('app.is_admin', true) = 'true'
                OR COALESCE(current_setting('app.current_org_id', true), '')
                  = organization_id::text
              )
            """
        )


def downgrade():
    for table in _TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    op.drop_column('organization', 'is_active')
