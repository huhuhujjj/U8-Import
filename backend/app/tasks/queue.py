"""Transactional enqueue: callers commit the job and queue row together."""
import os
from fastapi import HTTPException
from sqlalchemy import select, func, text
from app.business.purchase_order import digest
from app.models.entities import QueueTask, now

def target_key(header):
    return digest(header.get('_target', {'mode': 'MOCK'}))

def enqueue(db, job, kind):
    import shutil
    from app.observability import log_dir
    folder=log_dir();folder.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(folder).free<1024**3:
        raise HTTPException(503,'磁盘空间不足，已暂停接收新任务')
    target = target_key(job.header)
    db.execute(text('SELECT pg_advisory_xact_lock(:k)'), {'k': int(digest(['enqueue',target])[:15],16)})
    task = db.scalar(select(QueueTask).where(QueueTask.job_id==job.id, QueueTask.kind==kind))
    if task and task.status in ('PENDING','RUNNING'):
        return task
    count = db.scalar(select(func.count()).select_from(QueueTask).where(
        QueueTask.target==target, QueueTask.status.in_(['PENDING','RUNNING'])))
    if count >= max(1, int(os.getenv('QUEUE_CAPACITY', '100'))):
        raise HTTPException(503, '任务队列已满，请稍后再提交', headers={'Retry-After':'30'})
    if task is None:
        task = QueueTask(job_id=job.id, kind=kind, target=target)
        db.add(task)
    task.status='PENDING'
    task.attempts=0
    task.available_at=task.updated_at=now()
    task.last_error=''
    return task
