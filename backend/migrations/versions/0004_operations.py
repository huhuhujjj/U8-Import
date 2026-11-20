"""Durable queue and worker health, preserving existing business records."""
from alembic import op
revision = '0004'
down_revision = '0003'
branch_labels = depends_on = None

def upgrade():
    op.execute('''CREATE TABLE queue_tasks (
        id VARCHAR(36) PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL,
        job_id VARCHAR(36) NOT NULL REFERENCES import_jobs(id), kind VARCHAR NOT NULL,
        target VARCHAR NOT NULL, status VARCHAR NOT NULL, attempts INTEGER NOT NULL,
        available_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
        last_error VARCHAR NOT NULL, UNIQUE(job_id,kind))''')
    for col in ('job_id', 'target', 'status'):
        op.execute(f'CREATE INDEX ix_queue_tasks_{col} ON queue_tasks ({col})')
    op.execute('''CREATE TABLE worker_heartbeats (
        id VARCHAR PRIMARY KEY, target VARCHAR NOT NULL,
        seen_at TIMESTAMPTZ NOT NULL, job_id VARCHAR)''')
    op.execute('CREATE INDEX ix_worker_heartbeats_target ON worker_heartbeats(target)')

def downgrade():
    op.drop_table('worker_heartbeats')
    op.drop_table('queue_tasks')
