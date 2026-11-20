import json
import logging
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_api import env, data
from app.main import create_app


def test_web_queues_and_worker_completes(env):
    _, mock, factory = env
    with TestClient(create_app(factory, mock, queued=True)) as api:
        jid = api.post('/api/imports', json=data(1)).json()['id']
        assert api.post(f'/api/imports/{jid}/validate').json()['status'] == 'VALIDATING'
        assert mock.create_calls == 0
        from app.tasks.worker import Worker
        worker = Worker(factory, mock)
        assert worker.tick()
        assert api.get(f'/api/imports/{jid}/status').json()['status'] == 'READY_TO_CONFIRM'
        assert api.post(f'/api/imports/{jid}/confirm').json()['status'] == 'QUEUED'
        assert mock.create_calls == 0
        assert worker.tick()
        assert api.get(f'/api/imports/{jid}/status').json()['success_count'] == 1
        assert not worker.tick()
        assert mock.create_calls == 1


def test_queue_full_rolls_back_validation(env, monkeypatch):
    _, mock, factory = env
    monkeypatch.setenv('QUEUE_CAPACITY', '1')
    with TestClient(create_app(factory, mock, queued=True)) as api:
        a = api.post('/api/imports', json=data(1)).json()['id']
        b = api.post('/api/imports', json=data(1)).json()['id']
        assert api.post(f'/api/imports/{a}/validate').status_code == 200
        assert api.post(f'/api/imports/{b}/validate').status_code == 503
        assert api.get(f'/api/imports/{b}/status').json()['status'] == 'UPLOADED'


def test_logging_redacts_and_rotates(tmp_path, monkeypatch):
    monkeypatch.setenv('U8_APP_SECRET', 'sentinel-private-value')
    from app.observability import JsonFormatter
    from logging.handlers import RotatingFileHandler
    handler = RotatingFileHandler(tmp_path/'test.jsonl', maxBytes=400, backupCount=2, encoding='utf8')
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger('rotation-test')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        for _ in range(30):
            logger.info('token=abc123 sentinel-private-value', extra={'job_id':'job-1'})
    finally:
        handler.close()
        logger.removeHandler(handler)
    files = list(tmp_path.glob('test.jsonl*'))
    assert len(files) == 3
    for file in files:
        for line in file.read_text(encoding='utf8').splitlines():
            assert 'sentinel-private-value' not in line and 'abc123' not in line
            assert json.loads(line)['job_id'] == 'job-1'

def test_crashed_attempt_resumes_and_only_creates_once(env):
    from app.tasks.worker import Worker
    from app.models.entities import QueueTask, MockOrder, now
    _, mock, factory=env
    with TestClient(create_app(factory,mock,queued=True)) as api:
        jid=api.post('/api/imports',json=data(1)).json()['id']
        api.post(f'/api/imports/{jid}/validate')
        Worker(factory,mock).tick()
        api.post(f'/api/imports/{jid}/confirm')
        original=mock.create_purchase_order
        def crash(key,body):
            original(key,body)
            raise KeyboardInterrupt('process death after remote commit')
        mock.create_purchase_order=crash
        import pytest
        with pytest.raises(KeyboardInterrupt): Worker(factory,mock).tick()
        mock.create_purchase_order=original
        assert Worker(factory,mock).tick()
        assert api.get(f'/api/imports/{jid}/status').json()['status']=='COMPLETED'
        with factory() as db:
            assert len(list(db.scalars(select(MockOrder))))==1
        assert mock.create_calls==1

def test_concurrent_workers_do_not_duplicate(env):
    from concurrent.futures import ThreadPoolExecutor
    from app.tasks.worker import Worker
    _,mock,factory=env
    with TestClient(create_app(factory,mock,queued=True)) as api:
        jid=api.post('/api/imports',json=data(1)).json()['id']
        api.post(f'/api/imports/{jid}/validate');Worker(factory,mock).tick()
        api.post(f'/api/imports/{jid}/confirm')
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _:Worker(factory,mock).tick(),range(2)))
        assert api.get(f'/api/imports/{jid}/status').json()['success_count']==1
        assert mock.create_calls==1

def test_operations_flags_missing_worker_and_backlog(env):
    _,mock,factory=env
    with TestClient(create_app(factory,mock,queued=True)) as api:
        report=api.get('/api/operations').json()
        assert report['database']=='ok'
        assert 'worker_offline' in [a['code'] for a in report['alerts']]
        from app.tasks.worker import Worker
        Worker(factory,mock).heartbeat()
        report=api.get('/api/operations').json()
        assert 'worker_offline' not in [a['code'] for a in report['alerts']]

def test_dead_task_after_bounded_retries(env):
    from app.tasks.worker import Worker
    from app.models.entities import QueueTask, now
    _,mock,factory=env
    def outage(code): raise OSError('simulated vendor outage')
    mock.get_vendor=outage
    with TestClient(create_app(factory,mock,queued=True)) as api:
        jid=api.post('/api/imports',json=data(1)).json()['id']
        api.post(f'/api/imports/{jid}/validate')
        worker=Worker(factory,mock)
        for _ in range(3):
            worker.tick()
            with factory() as db:
                task=db.scalar(select(QueueTask).where(QueueTask.job_id==jid))
                task.available_at=now();db.commit()
        with factory() as db:
            task=db.scalar(select(QueueTask).where(QueueTask.job_id==jid))
            assert task.status=='DEAD' and task.attempts==3
        assert api.get(f'/api/imports/{jid}/status').json()['status']=='VALIDATION_FAILED'
        assert not worker.tick()
        assert mock.create_calls==0

def test_log_collection_filter_and_retention(tmp_path,monkeypatch):
    from app.operations import recent_logs,maintain_logs
    import os,time
    monkeypatch.setenv('LOG_DIR',str(tmp_path))
    active=tmp_path/'worker-1.jsonl'
    active.write_text(json.dumps({'time':'2026','job_id':'one','level':'ERROR','message':'safe'})+'\n',encoding='utf8')
    old=tmp_path/'api-2.jsonl.1';old.write_text('old')
    os.utime(old,(time.time()-20*86400,)*2)
    other=tmp_path/'business.csv';other.write_text('keep')
    assert len(recent_logs(job_id='one',level='ERROR'))==1
    assert recent_logs(job_id='two')==[]
    maintain_logs()
    assert not old.exists() and active.exists() and other.exists()

def test_failed_backup_preserves_previous_archive(tmp_path,monkeypatch):
    from app.backup import run_backup
    import subprocess
    import pytest
    tools=tmp_path/'bin';tools.mkdir()
    (tools/'pg_dump.exe').touch();(tools/'pg_restore.exe').touch()
    folder=tmp_path/'backups';folder.mkdir()
    marker=folder/'last-success.json';marker.write_text('previous-success')
    archive=folder/'u8-prior.dump';archive.write_bytes(b'previous')
    monkeypatch.setenv('PG_BIN',str(tools));monkeypatch.setenv('BACKUP_DIR',str(folder))
    def fail(args,**kwargs):
        assert 'PGPASSWORD' in kwargs['env']
        return subprocess.CompletedProcess(args,1,b'',b'sensitive database error')
    monkeypatch.setattr(subprocess,'run',fail)
    with pytest.raises(RuntimeError,match='pg_dump failed'):run_backup()
    assert marker.read_text()=='previous-success'
    assert archive.read_bytes()==b'previous'
    assert not list(folder.glob('*.partial'))
