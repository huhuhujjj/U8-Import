import os
import logging
import time
from sqlalchemy import delete,select,text
from sqlalchemy.exc import SQLAlchemyError
from app.models.entities import ImportError,OrderExecution,ErpResult
from app.business.purchase_order import payload
from app.services.import_service import get_job,rows_for,stats,audit,error
from app.integrations.u8.exceptions import U8BusinessError,U8UncertainError

log=logging.getLogger(__name__)
class ImportRunner:
    def __init__(self,session_factory,client,delays=(1,3,5)):
        self.factory=session_factory;self.client=client;self.delays=delays
        self.batch_size=int(os.getenv("IMPORT_BATCH_SIZE","50"))
        if not 1<=self.batch_size<=1000: raise ValueError("IMPORT_BATCH_SIZE must be 1..1000")
    def run(self,job_id):
        with self.factory.kw['bind'].connect() as connection:
            lock=int.from_bytes(job_id.encode()[:7],'big')
            acquired=connection.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':lock})
            connection.commit()
            if not acquired: return
            try: self._run(job_id)
            except Exception:
                log.exception('Import stopped; no further ERP writes for job %s',job_id)
                try:
                    with self.factory() as db:
                        job=get_job(db,job_id,True);job.status='SYSTEM_ERROR'
                        error(db,job,None,'SYSTEM_ERROR','执行中断，需核对结果后重试；详细信息见服务器日志')
                        audit(db,job,'SYSTEM_ERROR');db.commit()
                except SQLAlchemyError: log.exception('Database unavailable; persisted execution requires recovery')
            finally:
                connection.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':lock});connection.commit()
    def _run(self,job_id):
        with self.factory() as db:
            job=get_job(db,job_id,True)
            if job.status not in ('QUEUED','PROCESSING','SYSTEM_ERROR'): return
            execution=db.scalar(select(OrderExecution).where(OrderExecution.job_id==job_id))
            if not execution: raise RuntimeError('Missing durable execution reservation')
            rows=rows_for(db,job_id);body=payload(job.header,rows);key=job.order_key
            job.status='PROCESSING';execution.status='PROCESSING'
            for row in rows:
                if row.status!='SUCCESS': row.status='PROCESSING'
            audit(db,job,'START');db.commit()
        try: result=self.client.query_purchase_order(key)
        except U8BusinessError as exc:
            self._failure(job_id,'FAILED_BUSINESS',str(exc));return
        except U8UncertainError as exc:
            self._failure(job_id,'RECONCILIATION_REQUIRED',str(exc));return
        if result:
            self._success(job_id,result,body);return
        for attempt in range(len(self.delays)+1):
            try:
                result=self.client.create_purchase_order(key,body)
                self._success(job_id,result,body);return
            except U8BusinessError as exc:
                self._failure(job_id,'FAILED_BUSINESS',str(exc));return
            except U8UncertainError as exc:
                try: result=self.client.query_purchase_order(key)
                except U8BusinessError as query_exc:
                    self._failure(job_id,'FAILED_BUSINESS',str(query_exc));return
                except U8UncertainError:
                    self._failure(job_id,'RECONCILIATION_REQUIRED','写入结果不明，回查不可用；禁止盲目重建');return
                if result:
                    self._success(job_id,result,body);return
                if attempt==len(self.delays):
                    self._failure(job_id,'FAILED_RETRY_EXHAUSTED',str(exc));return
                with self.factory() as db:
                    job=get_job(db,job_id,True)
                    for row in rows_for(db,job_id): row.retry_count+=1;row.status='RETRYING'
                    audit(db,job,'AUTO_RETRY',{'attempt':attempt+1});db.commit()
                time.sleep(self.delays[attempt])
    def _success(self,job_id,result,body):
        mode=body['header'].get('_target',{}).get('mode','MOCK')
        if not result or not result.get('id') or result.get('mode')!=mode or result.get('payload')!=body:
            self._failure(job_id,'RECONCILIATION_REQUIRED','回查订单内容或最终业务结果不匹配');return
        with self.factory() as db:
            pending=[row.id for row in rows_for(db,job_id) if row.status!='SUCCESS']
        for offset in range(0,len(pending),self.batch_size):
            batch=set(pending[offset:offset+self.batch_size])
            with self.factory() as db:
                job=get_job(db,job_id,True)
                for row in rows_for(db,job_id):
                    if row.id not in batch or row.status=='SUCCESS': continue
                    row.status='SUCCESS'
                    db.add(ErpResult(job_id=job_id,row_id=row.id,request_data={'order_key':job.order_key,'header':job.header,'entry':row.normalized_data},response_data={'id':result['id'],'mode':mode},erp_business_id=result['id'],status='SUCCESS'))
                db.flush();stats(db,job);audit(db,job,'RESULT_BATCH',{'count':len(batch)})
                db.commit()
        with self.factory() as db:
            job=get_job(db,job_id,True)
            # A retry may follow one or more failed attempts.  Once the
            # remote order has been reconciled and every row is successful,
            # old attempt errors must not remain visible as current failures.
            db.execute(delete(ImportError).where(ImportError.job_id==job_id))
            execution=db.scalar(select(OrderExecution).where(OrderExecution.job_id==job_id))
            execution.status='SUCCESS';execution.erp_business_id=result['id']
            stats(db,job);job.status='COMPLETED';audit(db,job,'COMPLETE');db.commit()
    def _failure(self,job_id,code,message):
        with self.factory() as db:
            job=get_job(db,job_id,True)
            execution=db.scalar(select(OrderExecution).where(OrderExecution.job_id==job_id));execution.status=code
            for row in rows_for(db,job_id):
                if row.status=='SUCCESS': continue
                row.status='RECONCILIATION_REQUIRED' if code=='RECONCILIATION_REQUIRED' else 'FAILED'
                error(db,job,row,code,message)
                db.add(ErpResult(job_id=job_id,row_id=row.id,request_data={'order_key':job.order_key},response_data={'error':code,'message':message},status=code))
            db.flush();stats(db,job);job.status='COMPLETED_WITH_ERRORS';audit(db,job,code);db.commit()
