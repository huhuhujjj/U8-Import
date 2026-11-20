"""Read-only operations snapshot and local alert monitor; no ERP requests."""
import json
import logging
import os
import shutil
import time
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select, func
from app.models.entities import QueueTask, WorkerHeartbeat, now
from app.observability import log_dir

def snapshot(factory,target):
    alerts=[]
    result={'database':'ok','queue':{},'workers':0,'alerts':alerts,'checked_at':now().isoformat()}
    try:
        with factory() as db:
            result['queue']=dict(db.execute(select(QueueTask.status,func.count()).where(QueueTask.target==target).group_by(QueueTask.status)).all())
            result['workers']=db.scalar(select(func.count()).select_from(WorkerHeartbeat).where(
                WorkerHeartbeat.target==target,WorkerHeartbeat.seen_at>now()-timedelta(seconds=30)))
            oldest=db.scalar(select(func.min(QueueTask.created_at)).where(QueueTask.target==target,QueueTask.status=='PENDING'))
            result['oldest_pending_seconds']=max(0,int((now()-oldest).total_seconds())) if oldest else 0
        if not result['workers']: alerts.append({'code':'worker_offline','message':'Worker 心跳超过30秒未更新'})
        if result['queue'].get('DEAD',0): alerts.append({'code':'dead_tasks','message':'存在隔离失败任务，请查看任务错误后人工处理'})
        if result['oldest_pending_seconds']>300: alerts.append({'code':'queue_backlog','message':'任务排队超过5分钟'})
    except Exception:
        result['database']='unavailable'
        alerts.append({'code':'database_unavailable','message':'数据库或队列表不可用，请检查连接与迁移'})
    folder=log_dir();folder.mkdir(parents=True,exist_ok=True)
    free=shutil.disk_usage(folder).free
    result['disk_free_bytes']=free
    if free<1024**3: alerts.append({'code':'disk_low','message':'日志磁盘剩余空间不足1GB'})
    backup=Path(os.getenv('BACKUP_DIR',str(Path(__file__).resolve().parents[2]/'backups')))/'last-success.json'
    if not backup.exists() or time.time()-backup.stat().st_mtime>36*3600:
        alerts.append({'code':'backup_stale','message':'过去36小时无成功备份记录'})
    result['healthy']=not alerts
    return result

def maintain_logs(folder=None):
    """Remove only our old .jsonl files; never traverse outside the configured directory."""
    folder=Path(folder or log_dir()).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    files=[p for p in folder.glob('*.jsonl*') if p.is_file() and not p.is_symlink()
           and p.name.split('-')[0] in ('api','worker','monitor')]
    total=sum(p.stat().st_size for p in files)
    for file in sorted(files,key=lambda p:p.stat().st_mtime):
        age=time.time()-file.stat().st_mtime
        if age>14*86400 or (total>512*1024**2 and age>3600):
            size=file.stat().st_size
            try: file.unlink();total-=size
            except OSError: pass  # Windows protects an active process's file.

def recent_logs(limit=100, job_id='', level=''):
    """Bounded local collection across API/worker/monitor, no arbitrary file paths."""
    folder=log_dir()
    records=[]
    files=sorted((p for p in folder.glob('*.jsonl') if not p.is_symlink()),key=lambda p:p.stat().st_mtime,reverse=True)[:20]
    for file in files:
        if file.name.split('-')[0] not in ('api','worker','monitor'): continue
        try:
            with file.open('rb') as stream:
                size=file.stat().st_size
                stream.seek(max(0,size-128*1024))
                if size>128*1024: stream.readline()
                for line in stream:
                    try: record=json.loads(line)
                    except (ValueError,UnicodeDecodeError): continue
                    if record.get('environment')=='test': continue
                    if job_id and record.get('job_id')!=job_id: continue
                    if level and record.get('level')!=level: continue
                    records.append(record)
        except OSError: continue
    return sorted(records,key=lambda r:r.get('time',''),reverse=True)[:limit]

def main():
    from app.db.session import Session
    from app.tasks.queue import target_key
    from app.observability import configure_logging
    from app.integrations.u8.live import LiveU8Client
    configure_logging('monitor')
    if os.getenv('U8_MODE','MOCK')=='U8':
        client=LiveU8Client(Session);target=target_key({'_target':client.target})
    else: target=target_key({})
    previous=None
    last_backup_attempt=0
    while True:
        try:
            result=snapshot(Session,target)
            current=tuple(sorted(a['code'] for a in result['alerts']))
            if current!=previous:
                logging.getLogger('u8.monitor').log(logging.ERROR if current else logging.INFO,
                    'operations_alerts: %s', ','.join(current) or 'recovered',extra={'event':'operations_alert'})
                previous=current
            maintain_logs()
            if os.getenv('AUTO_BACKUP','0')=='1' and time.time()-last_backup_attempt>3600:
                folder=Path(os.getenv('BACKUP_DIR',str(Path(__file__).resolve().parents[2]/'backups')))
                marker=folder/'last-success.json'
                if not marker.exists() or time.time()-marker.stat().st_mtime>24*3600:
                    last_backup_attempt=time.time()
                    from app.backup import run_backup
                    run_backup()
                    logging.getLogger('u8.monitor').info('backup_completed',extra={'event':'backup'})
        except Exception: logging.getLogger('u8.monitor').exception('monitor_failed')
        time.sleep(15)

if __name__=='__main__': main()
