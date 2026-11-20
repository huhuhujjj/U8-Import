import sys,json,time,uuid,platform,importlib.metadata
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import select,func,text
from fastapi.testclient import TestClient
from app.main import create_app
from app.db.session import Session,engine
from app.models.entities import ImportRow,ErpResult,MockOrder,ImportError
root=Path(__file__).resolve().parents[1]
app=create_app();results=[]
with TestClient(app) as api:
    for n in (10,100,300):
        data=json.loads((root/f'test-data/payload_{n}.json').read_text())
        parse_ms=data.pop('parse_ms')
        data['header']={'order_reference':'BENCH-'+uuid.uuid4().hex,'vendor_code':'VENDOR-001','order_date':'2026-09-18','price_mode':'EXCLUSIVE'}
        before=app.state.runner.client.create_calls
        started=time.perf_counter()
        r=api.post('/api/imports',json=data);r.raise_for_status();id=r.json()['id']
        r=api.post(f'/api/imports/{id}/validate');r.raise_for_status()
        # Validation is asynchronous in the production app.  Wait for its
        # terminal state before recording metrics or confirming the job.
        deadline=time.monotonic()+30
        while True:
            state=api.get(f'/api/imports/{id}/status').json()
            if state['status'] not in ('UPLOADED','VALIDATING'):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f'validation timeout for {id}')
            time.sleep(0.05)
        valid=state['valid_count']
        r=api.post(f'/api/imports/{id}/confirm');r.raise_for_status()
        job=api.get(f'/api/imports/{id}/status').json()
        seconds=time.perf_counter()-started+parse_ms/1000
        with Session() as db:
            states=dict(db.execute(select(ImportRow.status,func.count()).where(ImportRow.job_id==id).group_by(ImportRow.status)).all())
            retries=db.scalar(select(func.sum(ImportRow.retry_count)).where(ImportRow.job_id==id))
            erp=db.scalar(select(ErpResult).where(ErpResult.job_id==id,ErpResult.status=='SUCCESS'))
            order=db.get(MockOrder,erp.erp_business_id) if erp else None
            verified=bool(order and len(order.payload['entries'])==n)
            error_count=db.scalar(select(func.count()).select_from(ImportError).where(ImportError.job_id==id))
        assert job['success_count']==n and job['failed_count']==0 and job['skipped_count']==0 and states=={'SUCCESS':n} and verified
        results.append({'file':data['file_name'],'job_id':id,'total':n,'valid':valid,'success':job['success_count'],'failed':0,'skipped':0,'unknown':0,'mapping':data['mapping'],'validation':'PASS','mock_create_calls':app.state.runner.client.create_calls-before,'real_u8_http_calls':0,'retry_count':retries,'elapsed_seconds':round(seconds,3),'average_ms_per_row':round(seconds*1000/n,3),'file_parse_ms':round(parse_ms,3),'database_states':states,'error_count':error_count,'mock_order_verified':verified})
with engine.connect() as conn:pg=conn.scalar(text('SHOW server_version'))
report={'time':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'python':sys.version.split()[0],'postgresql':pg,'versions':{p:importlib.metadata.version(p) for p in ['fastapi','sqlalchemy','alembic','psycopg','pytest']},'results':results,'status':'LOCAL_TEST_PASS','real_u8_integration':'NOT_RUN'}
(root/'docs/benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
