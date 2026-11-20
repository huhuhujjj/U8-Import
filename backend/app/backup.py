"""Custom-format PostgreSQL backup. A success marker is written only after archive validation."""
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.engine import make_url

def run_backup():
    from app.db.session import DATABASE_URL
    url=make_url(DATABASE_URL)
    folder=Path(os.getenv('BACKUP_DIR',str(Path(__file__).resolve().parents[2]/'backups'))).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    bin_dir=os.getenv('PG_BIN','')
    def executable(name):
        path=Path(bin_dir)/(name+'.exe') if bin_dir else shutil.which(name)
        if not path or not Path(path).is_file(): raise RuntimeError('Set PG_BIN to PostgreSQL bin directory')
        return str(path)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    temp=folder/f'u8-{stamp}.partial'; final=temp.with_suffix('.dump')
    env=os.environ.copy();env['PGPASSWORD']=url.password or '';env['PGCONNECT_TIMEOUT']='10'
    base=['-h',url.host or '127.0.0.1','-p',str(url.port or 5432),'-U',url.username or 'postgres']
    try:
        result=subprocess.run([executable('pg_dump'),*base,'-d',url.database,'-Fc','-f',str(temp)],env=env,capture_output=True,timeout=600)
        if result.returncode: raise RuntimeError('pg_dump failed; verify database availability and permissions')
        result=subprocess.run([executable('pg_restore'),'--list',str(temp)],env=env,capture_output=True,timeout=60)
        if result.returncode or temp.stat().st_size==0: raise RuntimeError('Backup archive validation failed')
        temp.replace(final)
        marker=folder/'last-success.tmp'
        marker.write_text(json.dumps({'time':stamp,'file':final.name,'bytes':final.stat().st_size}),encoding='utf8')
        marker.replace(folder/'last-success.json')
        # Retain 30 days; remove only our exact archive files in this directory.
        for old in folder.glob('u8-*.dump'):
            if not old.is_symlink() and old.is_file() and time.time()-old.stat().st_mtime>30*86400:
                old.unlink()
        return final
    finally:
        if temp.exists(): temp.unlink()

if __name__=='__main__': print(run_backup())
