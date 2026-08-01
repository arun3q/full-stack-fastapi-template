"""Add organizationmember.active (membership-scoped deactivation)

Revision ID: e3f5a7b9c1d2
Revises: d2e4f6a8b0c1
Create Date: 2026-08-01 10:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e3f5a7b9c1d2'
down_revision = 'd2e4f6a8b0c1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'organizationmember',
        sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade():
    op.drop_column('organizationmember', 'active')
