import json
import logging
from pathlib import Path
import pytest
from sqlalchemy import select, func
from test_api import env, data, prepare
from app.models.entities import ImportJob, QueueTask
from app.tasks.worker import Worker


@pytest.mark.parametrize('label', ['Amount', 'Total Amount', 'Grand Total', 'money', 'sum', 'Tax Amount', '含税金额'])
def test_amount_semantics_cannot_be_price(env, label):
    api, mock, _ = env
    p = data(1)
    p['source_headers']['M'] = label
    p['mapping']['price'] = 'M'
    p['rows'][0]['normalized_data']['price'] = '7'
    _, result = prepare(api, p)
    assert result['status'] == 'VALIDATION_FAILED'
    assert mock.create_calls == 0


def test_multiple_source_amounts_are_not_compared(env):
    api, _, _ = env
    p=data(1)
    p['source_headers'].update(M='不含税金额', N='含税金额')
    p['rows'][0]['raw_data']['N']='999'
    _, result=prepare(api,p)
    assert result['status']=='READY_TO_CONFIRM'


def test_explicit_price_basis_conflict_rejected(env):
    api, _, _ = env
    p=data(1);p['source_headers']['L']='含税单价'
    _, result=prepare(api,p)
    assert result['status']=='VALIDATION_FAILED'


def test_recovery_drains_more_legacy_jobs_than_capacity(env, monkeypatch):
    api, mock, factory=env
    monkeypatch.setenv('QUEUE_CAPACITY','1')
    ids=[api.post('/api/imports',json=data(1)).json()['id'] for _ in range(3)]
    with factory() as db:
        for jid in ids: db.get(ImportJob,jid).status='VALIDATING'
        db.commit()
    worker=Worker(factory,mock)
    for _ in ids:
        worker.recover_legacy()
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(QueueTask).where(QueueTask.status=='PENDING')) == 1
        assert worker.tick()
    assert all(api.get(f'/api/imports/{jid}/status').json()['status']=='READY_TO_CONFIRM' for jid in ids)


def test_test_logging_is_outside_runtime_collection():
    from app.observability import log_dir, JsonFormatter
    runtime=Path(__file__).resolve().parents[2]/'logs'
    assert not log_dir().resolve().is_relative_to(runtime.resolve())
    record=logging.LogRecord('test',logging.ERROR,'',0,'simulated outage',(),None)
    assert json.loads(JsonFormatter().format(record))['environment']=='test'


@pytest.mark.parametrize('mode', ['INCLUSIVE','EXCLUSIVE'])
@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '', '7.50', '2'])
def test_unused_source_amount_does_not_block_or_replace_price(env, amount, mode):
    api, _, _=env
    p=data(1);p['rows'][0]['raw_data']['M']=amount;p['header']['price_mode']=mode
    jid,result=prepare(api,p)
    assert result['status']=='READY_TO_CONFIRM'
    detail=api.get(f'/api/imports/{jid}').json()
    assert detail['rows'][0]['normalized_data']['price']=='3.5'
    assert detail['rows'][0]['raw_data']['M']==amount


def test_full_queue_does_not_block_recovery_or_drain(env, monkeypatch):
    from app.main import create_app
    from fastapi.testclient import TestClient
    _,mock,factory=env
    monkeypatch.setenv('QUEUE_CAPACITY','1')
    with TestClient(create_app(factory,mock,queued=True)) as api:
        a=api.post('/api/imports',json=data(1)).json()['id']
        b=api.post('/api/imports',json=data(1)).json()['id']
        api.post(f'/api/imports/{a}/validate')
        with factory() as db:
            db.get(ImportJob,b).status='VALIDATING';db.commit()
        worker=Worker(factory,mock)
        worker.recover_legacy()  # full, must not raise
        assert worker.tick()
        worker.recover_legacy()
        assert worker.tick()
        assert all(api.get(f'/api/imports/{jid}/status').json()['status']=='READY_TO_CONFIRM' for jid in (a,b))


def test_collector_excludes_test_records(tmp_path, monkeypatch):
    from app.operations import recent_logs
    monkeypatch.setenv('LOG_DIR',str(tmp_path))
    path=tmp_path/'worker-1.jsonl'
    path.write_text('\n'.join(json.dumps({'time':'2026','environment':mode,'level':'ERROR'}) for mode in ('test','u8','mock')),encoding='utf8')
    assert {r['environment'] for r in recent_logs()} == {'u8','mock'}
