"""Allowlisted JSON fields; process-local rotating files avoid Windows rename races."""
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from logging.handlers import RotatingFileHandler

SECRETS = set()

def redact(value):
    value = str(value)
    secrets = SECRETS | {os.getenv(k,'') for k in ('U8_APP_KEY','U8_APP_SECRET','DATABASE_URL')}
    for secret in sorted(filter(None,secrets), key=len, reverse=True):
        value = value.replace(secret, '[REDACTED]')
    value = re.sub(r'(?i)(token|app_key|app_secret|password|authorization)([\s\"\x27:=]+)[^\s,&\"\x27}]+', r'\1\2[REDACTED]', value)
    return value

class JsonFormatter(logging.Formatter):
    def format(self, record):
        result = {'time':datetime.now(timezone.utc).isoformat(), 'level':record.levelname,
                  'logger':record.name, 'pid':os.getpid(), 'message':redact(record.getMessage()),
                  'environment':os.getenv('U8_LOG_ENV',os.getenv('U8_MODE','MOCK')).lower()}
        for key in ('request_id','job_id','event','duration_ms','status_code','error_type'):
            if hasattr(record,key): result[key]=redact(getattr(record,key))
        # Exception type and traceback locations are useful without SQL parameters or credentials.
        if record.exc_info:
            import traceback
            result['error_type']=record.exc_info[0].__name__
            result['trace']=[f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in traceback.extract_tb(record.exc_info[2])]
        return json.dumps(result, ensure_ascii=False)

def log_dir():
    return Path(os.getenv('LOG_DIR', str(Path(__file__).resolve().parents[2]/'logs')))

def configure_logging(role):
    root=logging.getLogger()
    if any(getattr(h,'u8_handler',False) for h in root.handlers): return
    folder=log_dir(); folder.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(folder/f'{role}-{os.getpid()}.jsonl',
        maxBytes=5*1024*1024, backupCount=5, encoding='utf8')
    handler.u8_handler=True
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler); root.setLevel(logging.INFO)
    # HTTP clients can put authentication query strings in their default request log.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
