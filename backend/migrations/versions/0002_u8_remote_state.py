"""Persist U8 submission and asynchronous result identifiers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_executions', sa.Column('remote_state', JSONB(), nullable=True))


def downgrade():
    op.drop_column('order_executions', 'remote_state')
