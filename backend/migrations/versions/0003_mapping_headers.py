"""Bind saved mappings to the headers they were created from."""
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE field_mappings ADD COLUMN source_headers JSONB NOT NULL DEFAULT '{}'::jsonb")

def downgrade():
    op.execute('ALTER TABLE field_mappings DROP COLUMN source_headers')
