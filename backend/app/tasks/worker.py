"""Standalone PostgreSQL worker. One active consumer per target account.

The session advisory lock is held across the entire attempt. A stale timestamp
alone never permits a second consumer to run an in-flight ERP operation.
"""
import logging
import os
import signal
import threading
import time
import uuid
from datetime import timedelta
from sqlalchemy import select, text, delete, update
from app.models.entities import QueueTask, WorkerHeartbeat, ImportJob, ImportError, OrderExecution, now
from app.business.purchase_order import digest
from app.services.import_service import validate_job, get_job, error, audit
from app.tasks.import_tasks import ImportRunner
from app.tasks.queue import target_key, enqueue
from app.integrations.u8.exceptions import U8BusinessError

log=logging.getLogger('u8.worker')

class Worker:
    def __init__(self, factory, client):
        self.factory=factory
        self.client=client
        self.target=target_key({'_target':client.target} if getattr(client,'mode','MOCK')=='U8' else {})
        self.id=uuid.uuid4().hex
        self.job_id=None
        self.started=None
        self.failures=0
        self.runner=ImportRunner(factory,client)
        self.stop=threading.Event()

    def heartbeat(self):
        with self.factory() as db:
            row=db.get(WorkerHeartbeat,self.id)
            if row is None:
                row=WorkerHeartbeat(id=self.id,target=self.target)
                db.add(row)
            row.seen_at=now(); row.job_id=self.job_id
            db.commit()

    def recover_legacy(self):
        # Use the same transaction lock as enqueue; fill only available slots.
        # Repeat before each tick so consumption frees space for the next batch.
        from sqlalchemy import func, exists, case
        with self.factory() as db:
            db.execute(text('SELECT pg_advisory_xact_lock(:k)'),
                       {'k':int(digest(['enqueue',self.target])[:15],16)})
            active=db.scalar(select(func.count()).select_from(QueueTask).where(
                QueueTask.target==self.target,QueueTask.status.in_(['PENDING','RUNNING'])))
            available=max(1,int(os.getenv('QUEUE_CAPACITY','100')))-active
            if available<=0: return
            kind=case((ImportJob.status=='VALIDATING','VALIDATE'),else_='EXECUTE')
            target_filter=(ImportJob.header['_target']==self.client.target) if getattr(self.client,'mode','MOCK')=='U8' else (
                func.coalesce(ImportJob.header['_target']['mode'].astext,'MOCK')=='MOCK')
            jobs=db.scalars(select(ImportJob).where(
                ImportJob.status.in_(['VALIDATING','QUEUED','PROCESSING']),target_filter,
                ~exists(select(QueueTask.id).where(QueueTask.job_id==ImportJob.id,QueueTask.kind==kind)))
                .order_by(ImportJob.created_at).limit(available).with_for_update(skip_locked=True))
            from fastapi import HTTPException
            for job in jobs:
                try:
                    enqueue(db,job,'VALIDATE' if job.status=='VALIDATING' else 'EXECUTE')
                except HTTPException as exc:
                    if exc.status_code != 503: raise
                    # Admission (e.g. disk space) must not prevent existing work
                    # from draining; preserve already enqueued jobs in this batch.
                    break
            db.commit()

    def tick(self):
        self.heartbeat()
        lock=int(digest(['worker',self.target])[:15],16)
        with self.factory.kw['bind'].connect() as conn:
            acquired=conn.scalar(text('SELECT pg_try_advisory_lock(:k)'),{'k':lock})
            conn.commit()
            if not acquired: return False
            try:
                return self._process()
            finally:
                conn.execute(text('SELECT pg_advisory_unlock(:k)'),{'k':lock});conn.commit()

    def _process(self):
        with self.factory() as db:
            task=db.scalar(select(QueueTask).where(QueueTask.target==self.target,
                QueueTask.status.in_(['PENDING','RUNNING']),QueueTask.available_at<=now())
                .order_by(QueueTask.created_at).with_for_update(skip_locked=True).limit(1))
            if task is None: return False
            if task.attempts >= 3:
                task.status='DEAD';task.updated_at=now();task.last_error='attempt_limit'
                job=get_job(db,task.job_id)
                job.status='SYSTEM_ERROR' if task.kind=='EXECUTE' else 'VALIDATION_FAILED'
                error(db,job,None,'QUEUE_EXHAUSTED','任务恢复超过3次，已隔离，请人工核对')
                db.commit();return True
            task.status='RUNNING';task.attempts+=1;task.updated_at=now()
            task_id,job_id,kind=task.id,task.job_id,task.kind
            db.commit()
        self.job_id=job_id;self.started=time.monotonic()
        log.info('task_started',extra={'job_id':job_id,'event':kind})
        try:
            if kind=='VALIDATE':
                with self.factory() as db:
                    job=get_job(db,job_id)
                    if job.status=='VALIDATING':
                        db.execute(delete(ImportError).where(ImportError.job_id==job_id))
                        validate_job(db,job_id,self.client)
            else:
                self.runner.run(job_id)
            with self.factory() as db:
                job=get_job(db,job_id)
                if job.status=='SYSTEM_ERROR': raise RuntimeError('execution_interrupted')
                task=db.get(QueueTask,task_id)
                task.status='DONE' if job.status in ('READY_TO_CONFIRM','COMPLETED') else 'DEAD'
                task.updated_at=now()
                task.last_error='' if task.status=='DONE' else job.status
                execution=db.scalar(select(OrderExecution).where(OrderExecution.job_id==job_id))
                systemic=execution and execution.status in ('RECONCILIATION_REQUIRED','FAILED_RETRY_EXHAUSTED')
                self.failures=self.failures+1 if systemic else 0
                if self.failures>=3:
                    db.execute(update(QueueTask).where(QueueTask.target==self.target,QueueTask.status=='PENDING').values(available_at=now()+timedelta(seconds=60)))
                    log.error('u8_circuit_cooldown',extra={'job_id':job_id,'event':'circuit_open'})
                db.commit()
            log.info('task_finished',extra={'job_id':job_id,'event':task.status})
        except U8BusinessError as exc:
            # Validation business rejection must not be retried automatically.
            with self.factory() as db:
                task=db.get(QueueTask,task_id);task.status='DEAD';task.updated_at=now();task.last_error='U8BusinessError'
                job=get_job(db,job_id);job.status='VALIDATION_FAILED'
                from app.observability import redact
                error(db,job,None,'FAILED_BUSINESS',redact(exc))
                db.commit()
            log.exception('task_business_rejected',extra={'job_id':job_id})
        except Exception:
            self.failures+=1
            log.exception('task_interrupted',extra={'job_id':job_id})
            with self.factory() as db:
                task=db.get(QueueTask,task_id)
                task.status='DEAD' if task.attempts>=3 else 'PENDING'
                task.available_at=now()+timedelta(seconds=min(300,5*2**task.attempts))
                task.updated_at=now();task.last_error='infrastructure_failure'
                if self.failures>=3:
                    db.execute(update(QueueTask).where(QueueTask.target==self.target,QueueTask.status=='PENDING').values(available_at=now()+timedelta(seconds=60)))
                if task.status=='DEAD':
                    job=get_job(db,job_id)
                    job.status='SYSTEM_ERROR' if kind=='EXECUTE' else 'VALIDATION_FAILED'
                    error(db,job,None,'QUEUE_EXHAUSTED','基础设施故障重试耗尽，请查看运维告警')
                db.commit()
        finally:
            self.job_id=None;self.started=None
        return True

    def serve(self):
        from app.observability import configure_logging
        configure_logging('worker')
        def pulse():
            while not self.stop.wait(5):
                try: self.heartbeat()
                except Exception: log.exception('heartbeat_failed')
                # Terminate this process, not a thread that could keep writing U8.
                # A supervisor restarts it; durable submitted marker forces readback.
                if self.started and time.monotonic()-self.started>int(os.getenv('TASK_TIMEOUT_SECONDS','1800')):
                    log.critical('task_deadline_exceeded',extra={'job_id':self.job_id})
                    logging.shutdown();os._exit(2)
        threading.Thread(target=pulse,daemon=True).start()
        while not self.stop.is_set():
            try:
                self.recover_legacy()
                worked=self.tick()
                self.stop.wait(60 if self.failures>=3 else (0.1 if worked else 1))
            except Exception:
                log.exception('worker_unavailable')
                self.stop.wait(10)
        with self.factory() as db:
            row=db.get(WorkerHeartbeat,self.id)
            if row: db.delete(row);db.commit()

def main():
    from app.db.session import Session
    from app.integrations.u8.client import MockU8Client
    from app.integrations.u8.live import LiveU8Client
    mode=os.getenv('U8_MODE','MOCK')
    if mode not in ('MOCK','U8'): raise ValueError('Invalid U8_MODE')
    worker=Worker(Session,LiveU8Client(Session) if mode=='U8' else MockU8Client(Session))
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda *_:worker.stop.set())
    worker.serve()

if __name__=='__main__': main()
