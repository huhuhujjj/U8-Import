from sqlalchemy import select, func, text
from datetime import datetime
import secrets
from fastapi import HTTPException
from app.models.entities import ImportJob,ImportRow,ImportError,AuditLog,OrderExecution,ErpResult

# These states mean the remote result is not known yet. Terminal business
# failures can be retried with the same durable order reservation.
ACTIVE_EXECUTION_STATUSES = {'RESERVED', 'PROCESSING', 'RECONCILIATION_REQUIRED'}
RETRYABLE_EXECUTION_STATUSES = {'FAILED_BUSINESS', 'FAILED_RETRY_EXHAUSTED', 'SYSTEM_ERROR'}
from app.business.purchase_order import normalize,business_key,order_key,payload,digest
from concurrent.futures import ThreadPoolExecutor

def rows_for(db,id):
    return list(db.scalars(select(ImportRow).where(ImportRow.job_id==id).order_by(ImportRow.source_row)))
def get_job(db,id,lock=False):
    q=select(ImportJob).where(ImportJob.id==id)
    job=db.scalar(q.with_for_update() if lock else q)
    if not job: raise HTTPException(404,'任务不存在')
    return job

def stats(db,job):
    rows=rows_for(db,job.id)
    job.total_count=len(rows)
    job.valid_count=sum(r.status in ('VALID','PROCESSING','RETRYING','SUCCESS','SKIPPED_DUPLICATE') for r in rows)
    job.success_count=sum(r.status=='SUCCESS' for r in rows)
    job.failed_count=sum(r.status in ('INVALID','FAILED','RECONCILIATION_REQUIRED') for r in rows)
    job.skipped_count=sum(r.status=='SKIPPED_DUPLICATE' for r in rows)

def job_dict(job):
    result={k:getattr(job,k) for k in ('id','business_type','file_name','status','total_count','valid_count','success_count','failed_count','skipped_count','created_at','updated_at')}
    return result|{'header':{k:v for k,v in job.header.items() if k!='_target'},'mode':job.header.get('_target',{}).get('mode','MOCK')}
def row_dict(row):
    return {k:getattr(row,k) for k in ('id','source_row','line_reference','raw_data','normalized_data','status','business_key','retry_count')}
def audit(db,job,action,details=None): db.add(AuditLog(job_id=job.id,action=action,details=details or {}))
def error(db,job,row,code,message):
    db.add(ImportError(job_id=job.id,row_id=row.id if row else None,error_type=code,error_code=code,error_message=str(message)[:2000]))

def create_job(db,data,target=None):
    h=data.header.model_dump(mode='json',exclude_unset=True)
    h.setdefault('price_mode','EXCLUSIVE')
    if data.source_headers:
        h['_source_headers'] = dict(data.source_headers)
    if target:
        h['_target']=target
    if not str(h.get('order_reference') or '').strip():
        # Serialize candidate generation inside the transaction. This closes
        # the race where two requests choose the same generated reference
        # before either request has committed its ImportJob.
        while True:
            h['order_reference']=f"U8API{datetime.now():%Y%m%d}-{secrets.token_hex(6).upper()}"
            lock_key=int(digest(['generated-order-reference',h['order_reference']])[:15],16)
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':lock_key})
            if not db.scalar(select(ImportJob).where(ImportJob.order_key == order_key(h))): break
    if target and len(h['order_reference'])>30: raise HTTPException(422,'真实 U8 订单编号最多30字符')
    job=ImportJob(file_name=data.file_name,header=h,mapping=data.mapping,order_key=order_key(h),total_count=len(data.rows))
    db.add(job); db.flush()
    for r in data.rows:
        db.add(ImportRow(job_id=job.id,source_row=r.source_row,line_reference=r.line_reference,raw_data=r.raw_data,
                         normalized_data=r.normalized_data,business_key=business_key(h,r.line_reference)))
    audit(db,job,'CREATE'); db.commit()
    return job

def validate_job(db,id,client):
    job=get_job(db,id,True)
    if job.status not in ('UPLOADED','READY_TO_CONFIRM','VALIDATION_FAILED','VALIDATING'):
        raise HTTPException(409,'当前状态不能重新校验')
    job.status='VALIDATING'
    if hasattr(client, 'resolve_header_names'):
        # Resolve friendly department/person names during validation so an
        # invalid master value is reported before any purchase-order POST.
        # JSONB does not track in-place dictionary edits; assign a new value
        # so the resolved codes and the payload hash describe the same data.
        job.header = client.resolve_header_names(dict(job.header))
        db.flush()
    rows=rows_for(db,id); seen=set(); inventory={}
    vendor=client.get_vendor(job.header['vendor_code'])
    source_headers=job.header.get('_source_headers',{})
    from app.business.amount_validation import mapping_error
    problem=mapping_error(source_headers,job.mapping,job.header)
    if problem:
        for row in rows:
            row.status='INVALID'
            error(db,job,row,'FAILED_MAPPING',problem)
        stats(db,job); job.status='VALIDATION_FAILED'; audit(db,job,'VALIDATE'); db.commit(); return job
    codes=set()
    for r in rows:
        try:
            n=normalize(r.raw_data,job.mapping); codes.add(n['inventory_code'])
        except Exception: pass
    if codes:
        with ThreadPoolExecutor(max_workers=10) as ex:
            res=list(ex.map(client.get_inventory, codes))
        inventory=dict(zip(codes, res))
    for idx,r in enumerate(rows):
        r.status='VALID'
        try:
            normalized=normalize(r.raw_data,job.mapping)
            submitted=normalize(r.normalized_data,{k:k for k in ('inventory_code','quantity','price')})
            if normalized!=submitted: raise ValueError('映射结果与提交数据不一致')
            r.normalized_data=normalized
            code=normalized['inventory_code']
            if code not in inventory: inventory[code]=client.get_inventory(code)
            if not inventory[code]: raise ValueError(f'inventory_code: 物料 {code} 不存在')
            if not vendor: raise ValueError('vendor_code: 供应商不存在')
            signature=digest(normalized)
            if signature in seen: raise ValueError('文件内部存在完全重复明细，请确认后移除重复行')
            seen.add(signature)
        except ValueError as exc:
            r.status='INVALID'; error(db,job,r,'FAILED_VALIDATION',exc)
        if (idx+1)%10==0:
            db.flush(); stats(db,job); db.commit()
    job.payload_hash=digest(payload(job.header,rows))
    existing=db.scalar(select(OrderExecution).where(OrderExecution.order_key==job.order_key))
    if existing:
        if existing.payload_hash!=job.payload_hash:
            for r in rows:
                r.status='INVALID'; error(db,job,r,'BUSINESS_KEY_CONFLICT','同一订单标识已关联不同内容，禁止再次创建')
        elif existing.status=='SUCCESS':
            for r in rows: r.status='SKIPPED_DUPLICATE'
        elif existing.status in ACTIVE_EXECUTION_STATUSES:
            for r in rows:
                r.status='INVALID'; error(db,job,r,'ORDER_IN_PROGRESS','该订单已有未完成执行记录，请查看原任务')
        elif existing.status in RETRYABLE_EXECUTION_STATUSES:
            for r in rows:
                r.status='INVALID'; error(db,job,r,'ORDER_RETRY_ORIGINAL','原任务执行失败，请在原任务上重试，禁止创建新的执行记录')
    db.flush(); stats(db,job)
    job.status='VALIDATION_FAILED' if job.failed_count else 'READY_TO_CONFIRM'
    audit(db,job,'VALIDATE'); db.commit(); return job

def reserve_job(db,id,queued=False):
    job=get_job(db,id,True)
    if job.status in ('QUEUED','PROCESSING','COMPLETED','COMPLETED_WITH_ERRORS'):
        return job,False
    if job.status!='READY_TO_CONFIRM': raise HTTPException(409,'必须先完成业务校验')
    rows=rows_for(db,id)
    if not rows or any(r.status not in ('VALID','SKIPPED_DUPLICATE') for r in rows): raise HTTPException(409,'存在未通过校验的数据')
    # A transaction-level lock serializes cross-job confirmations of the same order.
    from sqlalchemy import text
    db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':int(job.order_key[:15],16)})
    existing=db.scalar(select(OrderExecution).where(OrderExecution.order_key==job.order_key))
    if existing:
        if existing.payload_hash!=job.payload_hash: raise HTTPException(409,'相同订单编号内容冲突')
        if existing.status=='SUCCESS':
            for r in rows: r.status='SKIPPED_DUPLICATE'
            stats(db,job); job.status='COMPLETED'; audit(db,job,'SKIP_DUPLICATE'); db.commit(); return job,False
        if existing.status not in RETRYABLE_EXECUTION_STATUSES:
            raise HTTPException(409,'同一订单正在处理或待核对，请查看原任务')
        existing.status='RESERVED'
        existing.erp_business_id=None
        existing.remote_state=None
        db.flush()
    db.add(OrderExecution(order_key=job.order_key,payload_hash=job.payload_hash,job_id=id))
    job.status='QUEUED'; audit(db,job,'CONFIRM')
    if queued:
        from app.tasks.queue import enqueue
        enqueue(db,job,'EXECUTE')
    db.commit(); return job,True

def retry_job(db,id,queued=False):
    job=get_job(db,id,True)
    if job.status in ('QUEUED','PROCESSING'): return job,False
    if job.status not in ('COMPLETED_WITH_ERRORS','SYSTEM_ERROR'): raise HTTPException(409,'此任务没有可重试的执行错误')
    rows=rows_for(db,id)
    execution=db.scalar(select(OrderExecution).where(OrderExecution.job_id==id))
    if not execution: raise HTTPException(409,'缺少执行记录，请先重新校验')
    for r in rows:
        if r.status!='SUCCESS': r.status='RETRYING'
    db.flush();stats(db,job)
    job.status='QUEUED'; audit(db,job,'RETRY')
    if queued:
        from app.tasks.queue import enqueue
        enqueue(db,job,'EXECUTE')
    db.commit(); return job,True
