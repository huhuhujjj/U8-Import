import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI,BackgroundTasks,HTTPException,Query
from fastapi.responses import JSONResponse
from sqlalchemy import select,text,func
from app.db.session import Session
from app.models.entities import ImportJob,ImportError,ImportRow,FieldMapping,AuditLog,OrderExecution
from app.api.schemas import ImportInput,MappingInput
from app.services.import_service import create_job,validate_job,reserve_job,retry_job,get_job,job_dict,row_dict,rows_for,error
from app.integrations.u8.client import MockU8Client
from app.tasks.import_tasks import ImportRunner
from app.integrations.u8.live import LiveU8Client
from app.integrations.u8.exceptions import U8BusinessError,U8UncertainError

def create_app(session_factory=None,client=None,queued=None):
    queued = session_factory is None if queued is None else queued
    mode='MOCK' if session_factory else os.getenv('U8_MODE','MOCK')
    if mode not in ('MOCK','U8'): raise RuntimeError('U8_MODE must be MOCK or U8')
    factory=session_factory or Session
    u8=client or (LiveU8Client(factory) if mode=='U8' else MockU8Client(factory))
    runner=ImportRunner(factory,u8,delays=(0,0,0) if session_factory else (1,3,5))
    @asynccontextmanager
    async def lifespan(app):
        if queued:
            from app.observability import configure_logging
            configure_logging('api')
            yield
            return
        with factory() as db:
            ids=[j.id for j in db.scalars(select(ImportJob).where(ImportJob.status.in_(['QUEUED','PROCESSING']))) if j.header.get('_target',{}).get('mode','MOCK')==mode]
        def recover():
            for id in ids: runner.run(id)
        thread=threading.Thread(target=recover,daemon=True);thread.start()
        yield
    app=FastAPI(title='U8 批量业务数据导入平台',lifespan=lifespan)
    app.state.runner=runner
    import logging, time, uuid
    @app.middleware('http')
    async def request_log(request, call_next):
        rid=uuid.uuid4().hex
        start=time.monotonic()
        try:
            response=await call_next(request)
        except Exception:
            logging.getLogger('u8.api').exception('request_failed',extra={'request_id':rid})
            raise
        response.headers['X-Request-ID']=rid
        logging.getLogger('u8.api').info('request_completed',extra={
            'request_id':rid,'job_id':request.path_params.get('id',''),
            'status_code':response.status_code,'duration_ms':round((time.monotonic()-start)*1000)})
        return response
    @app.exception_handler(U8BusinessError)
    def business_error(request,exc): return JSONResponse(status_code=422,content={'detail':str(exc)})
    @app.exception_handler(U8UncertainError)
    def uncertain_error(request,exc): return JSONResponse(status_code=503,content={'detail':str(exc)})
    def live():
        if mode!='U8': raise HTTPException(409,'当前为模拟模式，请使用真实 U8 启动脚本')
        return u8
    def check_target(db,id):
        job=get_job(db,id)
        if job.header.get('_target',{}).get('mode','MOCK')!=mode: raise HTTPException(409,'历史任务环境与当前环境不同，禁止执行')
        if mode=='U8' and job.header.get('_target')!=u8.target: raise HTTPException(409,'任务与当前账套配置不同')
    def present(db,job):
        result=job_dict(job)
        execution=db.scalar(select(OrderExecution).where(OrderExecution.order_key==job.order_key))
        result['erp_code']=execution.erp_business_id if execution else None
        return result
    @app.get('/api/u8/connection')
    def connection(): return live().connection()
    @app.get('/api/u8/orders')
    def orders(page:int=Query(1,ge=1),code:str='',date_begin:str='',date_end:str='',vendor:str=''):
        return live().list_orders(page,code,date_begin,date_end,vendor)
    @app.get('/api/u8/orders/{code}')
    def order(code:str): return live().order(code)
    @app.get('/api/u8/master/{kind}')
    def master(kind:str,page:int=Query(1,ge=1),name:str='',code:str=''):
        if kind not in ('vendor','inventory'): raise HTTPException(404,'主数据类型不存在')
        return live().master(kind,page,name,code)
    @app.get('/api/health')
    def health():
        with factory() as db: db.execute(text('SELECT 1'))
        return {'mode':mode,'database':'ok','account':u8.account if mode=='U8' else None}
    @app.get('/api/operations')
    def operations():
        from app.operations import snapshot
        from app.tasks.queue import target_key
        return snapshot(factory,target_key({'_target':u8.target} if mode=='U8' else {}))
    @app.get('/operations')
    def operations_page():
        from fastapi.responses import FileResponse
        return FileResponse(Path(__file__).with_name('operations.html'))
    @app.get('/api/operations/logs')
    def operations_logs(limit:int=Query(100,ge=1,le=500),job_id:str=Query('',max_length=100),level:str=Query('',pattern='^(|INFO|WARNING|ERROR|CRITICAL)$')):
        from app.operations import recent_logs
        return {'items':recent_logs(limit,job_id,level)}
    @app.get('/api/config')
    def get_config():
        if mode!='U8': return {'mode':'MOCK'}
        return {'mode':'U8','account':u8.account,'from_account':u8.from_account,'to_account':u8.to_account,'app_key':u8.key,'base_url':'https://api.yonyouup.com'}
    @app.post('/api/config')
    def set_config(data:dict):
        return {'ok':True,'received':data}
    @app.post('/api/imports')
    def create(data:ImportInput):
        with factory() as db: return job_dict(create_job(db,data,u8.target if mode=='U8' else None))
    @app.get('/api/imports')
    def history():
        with factory() as db: return [present(db,j) for j in db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(100))]
    @app.get('/api/imports/{id}')
    @app.get('/api/imports/{id}/preview')
    def detail(id:str):
        with factory() as db: return present(db,get_job(db,id))|{'rows':[row_dict(r) for r in rows_for(db,id)]}
    @app.get('/api/imports/{id}/status')
    def status(id:str):
        with factory() as db: return present(db,get_job(db,id))
    @app.post('/api/imports/{id}/validate')
    def validate(id:str,background:BackgroundTasks):
        with factory() as db:
            check_target(db,id)
            job=get_job(db,id,True)
            if job.status not in ('UPLOADED','READY_TO_CONFIRM','VALIDATION_FAILED'):
                raise HTTPException(409,'当前状态不能重新校验')
            if queued:
                from app.tasks.queue import enqueue
                job.status='VALIDATING'
                enqueue(db,job,'VALIDATE')
                db.commit()
                return present(db,job)
            if mode=='U8': u8.connection()
            job.status='VALIDATING'; db.commit()
        def run_validate():
            try:
                with factory() as db2: validate_job(db2,id,u8)
            except Exception as e:
                logging.getLogger('u8.validation').exception('validation_failed',extra={'job_id':id})
                with factory() as db3:
                    job=get_job(db3,id)
                    # A failed U8 master-data lookup is an infrastructure
                    # failure, not 85 bad business rows. Persist one task-level
                    # error and stop the progress UI at a retryable state.
                    error(db3,job,None,'U8_CONNECTION_FAILED',str(e))
                    job.status='VALIDATION_FAILED'
                    db3.add(AuditLog(job_id=id,action='VALIDATE_ERROR',details={'error':str(e)[:500]}))
                    db3.commit()
        # The injected session factory is used by the in-process test/benchmark
        # application.  Run validation before returning there so callers get a
        # stable terminal state and do not race the background task.  The real
        # server keeps validation asynchronous because U8 master-data lookups
        # may involve network calls and the frontend already polls the job.
        if session_factory is not None:
            run_validate()
        else:
            background.add_task(run_validate)
        with factory() as db: return present(db,get_job(db,id))
    @app.post('/api/imports/{id}/confirm')
    def confirm(id:str,background:BackgroundTasks):
        with factory() as db:
            check_target(db,id)
            job,start=reserve_job(db,id,queued=queued);result=job_dict(job)
        if start and not queued: background.add_task(runner.run,id)
        return result
    @app.post('/api/imports/{id}/retry')
    def retry(id:str,background:BackgroundTasks):
        with factory() as db:
            check_target(db,id)
            job,start=retry_job(db,id,queued=queued);result=job_dict(job)
        if start and not queued: background.add_task(runner.run,id)
        return result
    @app.get('/api/imports/{id}/errors')
    def errors(id:str):
        with factory() as db:
            get_job(db,id)
            records=db.execute(select(ImportError,ImportRow.source_row).outerjoin(ImportRow,ImportRow.id==ImportError.row_id).where(ImportError.job_id==id).order_by(ImportError.created_at))
            return [{'row_id':e.row_id,'source_row':line,'error_type':e.error_type,'error_code':e.error_code,'error_message':e.error_message} for e,line in records]
    @app.get('/api/mappings')
    def mappings():
        with factory() as db:
            groups={}
            for m in db.scalars(select(FieldMapping).where(FieldMapping.enabled==True).order_by(FieldMapping.version.desc())):
                entry=groups.setdefault((m.template_name,m.version),{'id':m.id,'template_name':m.template_name,'version':m.version,'mapping':{},'source_headers':m.source_headers or {},'enabled':True,'business_type':m.business_type})
                entry['mapping'][m.target_field]=m.source_field
            return list(groups.values())
    @app.post('/api/mappings')
    def save_mapping(data:MappingInput):
        from app.business.purchase_order import digest
        with factory() as db:
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':int(digest(data.template_name)[:15],16)})
            version=(db.scalar(select(func.max(FieldMapping.version)).where(FieldMapping.template_name==data.template_name)) or 0)+1
            entries=[FieldMapping(template_name=data.template_name,version=version,source_field=s,target_field=t,source_headers=data.source_headers) for t,s in data.mapping.items()]
            db.add_all(entries);db.add(AuditLog(action='SAVE_MAPPING',details={'name':data.template_name,'version':version}));db.commit()
            return {'id':entries[0].id,'template_name':data.template_name,'version':version,'mapping':data.mapping,'source_headers':data.source_headers,'enabled':True,'business_type':'PURCHASE_ORDER'}
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    dist=Path(__file__).resolve().parents[2]/'frontend'/'dist'
    if dist.is_dir(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app
app=create_app()
