import uuid
import pytest
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.db.session import engine
from app.models.entities import Base,MockOrder,ImportRow,OrderExecution,ErpResult
from app.integrations.u8.client import MockU8Client
from app.integrations.u8.exceptions import U8UncertainError,U8TemporaryError,U8BusinessError
from app.main import create_app

@pytest.fixture
def env():
    schema='test_'+uuid.uuid4().hex
    with engine.begin() as c: c.execute(text(f'CREATE SCHEMA {schema}'))
    test_engine=create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(test_engine)
    factory=sessionmaker(test_engine,expire_on_commit=False)
    mock=MockU8Client(factory)
    app=create_app(factory,mock)
    with TestClient(app) as api:
        yield api,mock,factory
    test_engine.dispose()
    with engine.begin() as c: c.execute(text(f'DROP SCHEMA {schema} CASCADE'))

def data(n=10,ref=None):
    return {'file_name':f'test_{n}.xlsx','mapping':{'inventory_code':'G','quantity':'K','price':'L'},
            'header':{'order_reference':ref or uuid.uuid4().hex,'vendor_code':'VENDOR-001','order_date':'2026-09-18','price_mode':'EXCLUSIVE'},
            'source_headers':{'G':'物料编码','K':'数量','L':'单价（元）','M':'金额（元）'},
            'rows':[{'source_row':i+1,'line_reference':str(i),'raw_data':{'G':f'MAT-{i:03d}','K':'2','L':'3.5','M':'7'},
                     'normalized_data':{'inventory_code':f'MAT-{i:03d}','quantity':'2','price':'3.5'}} for i in range(1,n+1)]}

def prepare(api,payload):
    r=api.post('/api/imports',json=payload)
    assert r.status_code==200,r.text
    id=r.json()['id']
    r=api.post(f'/api/imports/{id}/validate')
    assert r.status_code==200,r.text
    return id,r.json()

@pytest.mark.parametrize('n',[10,100,300])
def test_complete_flow_and_duplicate_confirm(env,n):
    api,mock,factory=env
    id,j=prepare(api,data(n))
    assert j['valid_count']==n
    assert api.post(f'/api/imports/{id}/confirm').status_code==200
    assert api.post(f'/api/imports/{id}/confirm').status_code==200
    job=api.get(f'/api/imports/{id}/status').json()
    assert (job['status'],job['success_count'],job['failed_count'],job['skipped_count'])==('COMPLETED',n,0,0)
    assert mock.create_calls==1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(MockOrder))==1
        assert db.scalar(select(func.count()).select_from(ImportRow).where(ImportRow.status=='SUCCESS'))==n
        assert db.scalar(select(func.count()).select_from(ErpResult))==n

def test_source_amount_mismatch_does_not_block_validation(env):
    api,mock,_=env
    p=data(1);p['rows'][0]['raw_data']['M']='999';p['rows'][0]['normalized_data']['price']='3.5'
    id,result=prepare(api,p)
    assert result['status']=='READY_TO_CONFIRM'
    assert api.get(f'/api/imports/{id}/errors').json()==[]
    assert mock.create_calls==0

def test_amount_column_cannot_be_mapped_as_unit_price(env):
    api,mock,_=env
    p=data(1);p['mapping']['price']='M';p['rows'][0]['normalized_data']['price']='7'
    id,result=prepare(api,p)
    assert result['status']=='VALIDATION_FAILED'
    assert '金额列' in api.get(f'/api/imports/{id}/errors').json()[0]['error_message']
    assert mock.create_calls==0


def test_generated_order_reference_retries_after_collision(env,monkeypatch):
    api,_,_=env
    values=iter(['ABCDEF123456','ABCDEF123456','FEDCBA654321'])
    monkeypatch.setattr('app.services.import_service.secrets.token_hex',lambda n:next(values))
    p=data(1);p['header']['order_reference']=''
    first=api.post('/api/imports',json=p);assert first.status_code==200,first.text
    second=api.post('/api/imports',json=p);assert second.status_code==200,second.text
    assert first.json()['header']['order_reference'] != second.json()['header']['order_reference']

@pytest.mark.parametrize('field,value',[('G',''),('K','abc'),('K','0'),('L','abc'),('G','MISSING')])
def test_bad_rows_block_entire_new_order(env,field,value):
    api,mock,_=env
    p=data();p['rows'][0]['raw_data'][field]=value
    p['rows'][0]['normalized_data'][{'G':'inventory_code','K':'quantity','L':'price'}[field]]=value
    id,j=prepare(api,p)
    assert j['failed_count']==1
    assert api.post(f'/api/imports/{id}/confirm').status_code==409
    assert len(api.get(f'/api/imports/{id}/errors').json())==1
    assert mock.create_calls==0

def test_history_duplicate_and_changed_payload_conflict(env):
    api,mock,_=env
    p=data();id,_=prepare(api,p);api.post(f'/api/imports/{id}/confirm')
    id,j=prepare(api,p)
    assert j['skipped_count']==10
    api.post(f'/api/imports/{id}/confirm')
    p['rows'][0]['raw_data']['K']='3';p['rows'][0]['normalized_data']['quantity']='3'
    _,j=prepare(api,p)
    assert j['failed_count']==10
    assert mock.create_calls==1

def test_internal_duplicates_are_not_silently_written(env):
    api,mock,_=env
    p=data();p['rows'][1]['raw_data']=p['rows'][0]['raw_data'];p['rows'][1]['normalized_data']=p['rows'][0]['normalized_data']
    _,j=prepare(api,p)
    assert j['failed_count']==1 and mock.create_calls==0

def test_timeout_after_creation_is_reconciled_without_recreate(env):
    api,mock,_=env
    original=mock.create_purchase_order
    def timeout(key,p):
        original(key,p)
        raise U8UncertainError('timeout after commit')
    mock.create_purchase_order=timeout
    id,_=prepare(api,data());api.post(f'/api/imports/{id}/confirm')
    assert api.get(f'/api/imports/{id}/status').json()['success_count']==10
    assert mock.create_calls==1

def test_unavailable_reconciliation_does_not_resubmit(env):
    api,mock,_=env
    def timeout(key,p):
        mock.create_calls+=1
        raise U8UncertainError('timeout')
    def unknown(key): raise U8UncertainError('query unavailable')
    mock.create_purchase_order=timeout; mock.query_purchase_order=unknown
    id,_=prepare(api,data());api.post(f'/api/imports/{id}/confirm')
    assert api.get(f'/api/imports/{id}/status').json()['failed_count']==10
    assert mock.create_calls==0 # pre-create reconciliation unavailable, so fail closed

def test_500_retry_exhaustion(env):
    api,mock,_=env
    def failing(key,p):
        mock.create_calls+=1
        raise U8TemporaryError('500')
    mock.create_purchase_order=failing
    id,_=prepare(api,data());api.post(f'/api/imports/{id}/confirm')
    assert mock.create_calls==4
    assert api.get(f'/api/imports/{id}/status').json()['failed_count']==10
    assert api.get(f'/api/imports/{id}/errors').json()[0]['error_code']=='FAILED_RETRY_EXHAUSTED'

def test_business_error_is_not_automatically_retried(env):
    api,mock,_=env
    def fail(key,p):
        mock.create_calls+=1;raise U8BusinessError('business reject')
    mock.create_purchase_order=fail
    id,_=prepare(api,data());api.post(f'/api/imports/{id}/confirm')
    assert mock.create_calls==1
    assert api.get(f'/api/imports/{id}/errors').json()[0]['error_code']=='FAILED_BUSINESS'

def test_two_drafts_same_order_only_one_write(env):
    api,mock,_=env
    p=data();a,_=prepare(api,p);b,_=prepare(api,p)
    api.post(f'/api/imports/{a}/confirm');api.post(f'/api/imports/{b}/confirm')
    assert mock.create_calls==1
    assert api.get(f'/api/imports/{b}/status').json()['skipped_count']==10

def test_confirm_requires_validation(env):
    api,mock,_=env
    id=api.post('/api/imports',json=data()).json()['id']
    assert api.post(f'/api/imports/{id}/confirm').status_code==409
    assert mock.create_calls==0

def test_database_result_failure_stops_and_retry_reconciles(env):
    from sqlalchemy import event
    from app.tasks.import_tasks import ImportRunner
    from app.services.import_service import reserve_job,retry_job
    api,mock,factory=env
    id,_=prepare(api,data())
    with factory() as db:reserve_job(db,id)
    fired=[False]
    def fail_result(conn,cursor,statement,parameters,context,executemany):
        if 'INSERT INTO erp_results' in statement and not fired[0]:
            fired[0]=True
            from sqlalchemy.exc import OperationalError
            raise OperationalError(statement,{},Exception('simulated database interruption'))
    event.listen(factory.kw['bind'],'before_cursor_execute',fail_result)
    runner=ImportRunner(factory,mock,delays=(0,0,0))
    try:runner.run(id)
    finally:event.remove(factory.kw['bind'],'before_cursor_execute',fail_result)
    assert api.get(f'/api/imports/{id}/status').json()['status']=='SYSTEM_ERROR'
    assert mock.create_calls==1
    with factory() as db:retry_job(db,id)
    runner.run(id)
    assert api.get(f'/api/imports/{id}/status').json()['success_count']==10
    assert mock.create_calls==1

def test_interrupted_process_recovery_queries_existing_order(env):
    from app.tasks.import_tasks import ImportRunner
    from app.services.import_service import reserve_job
    api,mock,factory=env
    id,_=prepare(api,data())
    with factory() as db:reserve_job(db,id)
    runner=ImportRunner(factory,mock,delays=(0,0,0))
    original=mock.create_purchase_order
    def crash(key,p):
        original(key,p)
        raise KeyboardInterrupt('simulated abrupt process interruption')
    mock.create_purchase_order=crash
    with pytest.raises(KeyboardInterrupt):runner.run(id)
    assert api.get(f'/api/imports/{id}/status').json()['status']=='PROCESSING'
    mock.create_purchase_order=original
    ImportRunner(factory,mock,delays=(0,0,0)).run(id)
    assert api.get(f'/api/imports/{id}/status').json()['success_count']==10
    assert mock.create_calls==1

def test_concurrent_cross_job_reservations_are_serialized(env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    from app.services.import_service import reserve_job
    api,mock,factory=env
    p=data();a,_=prepare(api,p);b,_=prepare(api,p);barrier=Barrier(2)
    def reserve(id):
        barrier.wait()
        with factory() as db:
            try:return reserve_job(db,id)[1]
            except HTTPException as exc:assert exc.status_code==409;return False
    with ThreadPoolExecutor(2) as pool:outcomes=list(pool.map(reserve,[a,b]))
    assert sorted(outcomes)==[False,True]
    with factory() as db:assert db.scalar(select(func.count()).select_from(OrderExecution))==1

def test_mapping_versions_and_different_order_same_items(env):
    api,mock,_=env
    m={'template_name':'test','mapping':data()['mapping']}
    assert api.post('/api/mappings',json=m).json()['version']==1
    assert api.post('/api/mappings',json=m).json()['version']==2
    assert len(api.get('/api/mappings').json())==2
    for _ in range(2):
        id,_=prepare(api,data());api.post(f'/api/imports/{id}/confirm')
    assert mock.create_calls==2

def test_partial_batch_result_failure_recovers_only_unrecorded_rows(env):
    from sqlalchemy import event
    from app.tasks.import_tasks import ImportRunner
    from app.services.import_service import reserve_job,retry_job
    api,mock,factory=env
    id,_=prepare(api,data(100))
    with factory() as db:reserve_job(db,id)
    calls=[0]
    def fail_second_batch(conn,cursor,statement,parameters,context,executemany):
        if 'INSERT INTO erp_results' in statement:
            calls[0]+=1
            if calls[0]==2:
                from sqlalchemy.exc import OperationalError
                raise OperationalError(statement,{},Exception('second result batch failed'))
    event.listen(factory.kw['bind'],'before_cursor_execute',fail_second_batch)
    runner=ImportRunner(factory,mock,delays=(0,0,0))
    try:runner.run(id)
    finally:event.remove(factory.kw['bind'],'before_cursor_execute',fail_second_batch)
    job=api.get(f'/api/imports/{id}/status').json()
    assert job['status']=='SYSTEM_ERROR' and job['success_count']==50
    with factory() as db:retry_job(db,id)
    runner.run(id)
    assert api.get(f'/api/imports/{id}/status').json()['success_count']==100
    assert mock.create_calls==1
    with factory() as db:assert db.scalar(select(func.count()).select_from(ErpResult).where(ErpResult.status=='SUCCESS'))==100


@pytest.mark.parametrize('named_header', [False, True])
@pytest.mark.parametrize('legacy', [False, True])
def test_live_adapter_full_task_persists_and_skips_duplicate(env,monkeypatch,named_header,legacy):
    import httpx,json
    from app.integrations.u8.live import LiveU8Client
    from app.api.schemas import ImportInput
    from app.services.import_service import create_job,validate_job,reserve_job
    from app.tasks.import_tasks import ImportRunner
    _,_,factory=env
    monkeypatch.setenv('U8_APP_KEY','test-key');monkeypatch.setenv('U8_APP_SECRET','test-secret')
    ledger=[];posts=[]
    def respond(request):
        path=request.url.path
        if path=='/system/token':result={'errcode':0,'token':{'id':'test-token'}}
        elif path=='/api/account/get':result={'errcode':0,'account':{'code':'999'}}
        elif path=='/api/department/batch_get':
            result={'errcode':0,'department':[{'code':'0502','name':'运营中心-采购部','endflag':'1'}]}
        elif path=='/api/person/batch_get':
            result={'errcode':0,'person':[{'code':'msk01016','name':'马俊鑫'}]}
        elif path.endswith('/batch_get') and ('inventory' in path or 'vendor' in path):
            kind='inventory' if 'inventory' in path else 'vendor'
            result={'errcode':0,kind:[{'code':request.url.params['code_begin']}]}
        elif path=='/api/purchaseorderlist/batch_get':result={'errcode':0,'purchaseorderlist':ledger}
        elif path=='/api/purchaseorder/get':result={'errcode':0,'purchaseorder':ledger[0]}
        elif path=='/api/purchaseorder/add':
            posts.append(request)
            order=json.loads(request.content)['purchaseorder'];order['code']='CG-AUTO-TEST'
            ledger.append(order);result={'errcode':0,'id':order['code']}
        else:raise AssertionError(path)
        return httpx.Response(200,json=result)
    client=LiveU8Client(factory,transport=httpx.MockTransport(respond))
    source=data(3,ref='LIVE-TASK-001')
    if named_header:
        source['header'].update(department='运营中心-采购部',employee='马俊鑫')
    sample=ImportInput.model_validate(source)
    with factory() as db:
        job=create_job(db,sample,client.target);id=job.id
        if legacy:
            with monkeypatch.context() as patch:
                patch.setattr(client,'resolve_header_names',lambda header:header)
                validate_job(db,id,client)
        else:
            validate_job(db,id,client)
        reserve_job(db,id)
    with factory() as db:
        from app.models.entities import ImportJob
        from app.business.purchase_order import digest,payload
        from app.services.import_service import rows_for
        job=db.get(ImportJob,id)
        assert job.payload_hash==digest(payload(job.header,rows_for(db,id)))
        if named_header and not legacy:
            assert job.header['deptcode']=='0502'
            assert job.header['personcode']=='msk01016'
    ImportRunner(factory,client,delays=()).run(id)
    with factory() as db:
        from app.models.entities import ImportJob
        job=db.get(ImportJob,id)
        assert job.status=='COMPLETED' and job.success_count==3
        execution=db.scalar(select(OrderExecution).where(OrderExecution.job_id==id))
        assert execution.erp_business_id=='CG-AUTO-TEST'
        assert execution.remote_state['submitted']
        result=client.query_purchase_order(job.order_key)
        assert result['payload']==payload(job.header,rows_for(db,id))
        client.create_purchase_order(job.order_key,result['payload'])
        repeat=create_job(db,sample,client.target)
        if legacy:
            with monkeypatch.context() as patch:
                patch.setattr(client,'resolve_header_names',lambda header:header)
                validate_job(db,repeat.id,client)
        else:
            validate_job(db,repeat.id,client)
        assert reserve_job(db,repeat.id)[1] is False
        assert repeat.skipped_count==3
    assert len(posts)==1
    if named_header:
        assert ledger[0]['deptcode']=='0502'
        assert ledger[0]['personcode']=='msk01016'
