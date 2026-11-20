import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class ImportJob(Identity, Base):
    __tablename__='import_jobs'
    business_type: Mapped[str] = mapped_column(default='PURCHASE_ORDER')
    file_name: Mapped[str]
    status: Mapped[str] = mapped_column(default='UPLOADED')
    total_count: Mapped[int] = mapped_column(default=0)
    valid_count: Mapped[int] = mapped_column(default=0)
    success_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    skipped_count: Mapped[int] = mapped_column(default=0)
    header: Mapped[dict] = mapped_column(JSONB)
    mapping: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(default='')
    order_key: Mapped[str] = mapped_column(index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
class ImportRow(Identity, Base):
    __tablename__='import_rows'
    __table_args__=(UniqueConstraint('job_id','line_reference'),)
    job_id: Mapped[str] = mapped_column(ForeignKey('import_jobs.id'),index=True)
    source_row: Mapped[int]
    line_reference: Mapped[str]
    raw_data: Mapped[dict] = mapped_column(JSONB)
    normalized_data: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(default='PENDING')
    business_key: Mapped[str] = mapped_column(index=True)
    retry_count: Mapped[int] = mapped_column(default=0)
class ImportError(Identity, Base):
    __tablename__='import_errors'
    job_id: Mapped[str] = mapped_column(ForeignKey('import_jobs.id'),index=True)
    row_id: Mapped[str|None] = mapped_column(ForeignKey('import_rows.id'),nullable=True)
    error_type: Mapped[str]
    error_code: Mapped[str]
    error_message: Mapped[str]
class ErpResult(Identity, Base):
    __tablename__='erp_results'
    job_id: Mapped[str] = mapped_column(ForeignKey('import_jobs.id'),index=True)
    row_id: Mapped[str] = mapped_column(ForeignKey('import_rows.id'))
    request_data: Mapped[dict] = mapped_column(JSONB)
    response_data: Mapped[dict] = mapped_column(JSONB)
    erp_business_id: Mapped[str|None]
    status: Mapped[str]
class FieldMapping(Identity, Base):
    __tablename__='field_mappings'
    __table_args__=(UniqueConstraint('template_name','version','target_field'),)
    business_type: Mapped[str] = mapped_column(default='PURCHASE_ORDER')
    template_name: Mapped[str]
    source_field: Mapped[str]
    target_field: Mapped[str]
    enabled: Mapped[bool] = mapped_column(Boolean,default=True)
    version: Mapped[int]
    source_headers: Mapped[dict] = mapped_column(JSONB, default=dict)
class AuditLog(Identity, Base):
    __tablename__='audit_logs'
    job_id: Mapped[str|None] = mapped_column(ForeignKey('import_jobs.id'),nullable=True)
    action: Mapped[str]
    operator: Mapped[str] = mapped_column(default='local-developer')
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
class OrderExecution(Identity, Base):
    __tablename__='order_executions'
    order_key: Mapped[str] = mapped_column(unique=True)
    payload_hash: Mapped[str]
    job_id: Mapped[str] = mapped_column(ForeignKey('import_jobs.id'))
    status: Mapped[str] = mapped_column(default='RESERVED')
    erp_business_id: Mapped[str|None]
    remote_state: Mapped[dict|None] = mapped_column(JSONB, nullable=True)
class MockOrder(Identity, Base):
    """Local simulated ERP ledger, NEVER real U8 data."""
    __tablename__='mock_u8_orders'
    order_key: Mapped[str] = mapped_column(unique=True)
    payload: Mapped[dict] = mapped_column(JSONB)

class QueueTask(Identity, Base):
    __tablename__ = 'queue_tasks'
    __table_args__ = (UniqueConstraint('job_id', 'kind'),)
    job_id: Mapped[str] = mapped_column(ForeignKey('import_jobs.id'), index=True)
    kind: Mapped[str]
    target: Mapped[str] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(default='PENDING', index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_error: Mapped[str] = mapped_column(default='')

class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeats'
    id: Mapped[str] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    job_id: Mapped[str|None]
