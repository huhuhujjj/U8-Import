"""Real TCP + separate Web/Worker processes, isolated PostgreSQL schema, MOCK only."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx
from test_api import env, data

def eventually(fn, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            result=fn()
            if result: return result
        except (httpx.TransportError,KeyError): pass
        time.sleep(.1)
    raise AssertionError('Timed out waiting for independent process')

def test_real_http_survives_web_restart(env,tmp_path):
    _,_,factory=env
    engine=factory.kw['bind']
    options=engine.dialect.create_connect_args(engine.url)[1]
    # Fixture engine search path lives in connect_args, not its URL.
    from sqlalchemy import text
    with engine.connect() as db: schema=db.scalar(text('SELECT current_schema()'))
    environment=os.environ.copy()
    environment.update(U8_MODE='MOCK',DATABASE_URL=engine.url.update_query_dict({'options':f'-csearch_path={schema}'}).render_as_string(hide_password=False),LOG_DIR=str(tmp_path/'logs'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    backend=Path(__file__).resolve().parents[1]
    children=[]
    def launch(*args):
        process=subprocess.Popen([sys.executable,*args],cwd=backend,env=environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        children.append(process);return process
    def stop(process):
        process.terminate();process.wait(timeout=10)
    try:
        web=launch('-m','uvicorn','app.main:app','--port',str(port))
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=10) as api:
            eventually(lambda:api.get('/api/health').status_code==200)
            jid=api.post('/api/imports',json=data(10)).json()['id']
            assert api.post(f'/api/imports/{jid}/validate').json()['status']=='VALIDATING'
            stop(web)
            web=launch('-m','uvicorn','app.main:app','--port',str(port))
            eventually(lambda:api.get('/api/health').status_code==200)
            assert api.get(f'/api/imports/{jid}/status').json()['status']=='VALIDATING'
            worker=launch('-m','app.tasks.worker')
            eventually(lambda:api.get(f'/api/imports/{jid}/status').json()['status']=='READY_TO_CONFIRM')
            stop(worker)
            assert api.post(f'/api/imports/{jid}/confirm').json()['status']=='QUEUED'
            worker=launch('-m','app.tasks.worker')
            eventually(lambda:api.get(f'/api/imports/{jid}/status').json()['status']=='COMPLETED')
            assert api.get(f'/api/imports/{jid}/status').json()['success_count']==10
            assert api.get('/operations').status_code==200
    finally:
        for process in children:
            if process.poll() is None: stop(process)
