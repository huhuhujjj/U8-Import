import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://u8local:u8local@127.0.0.1:55432/u8_import')
if not DATABASE_URL.startswith('postgresql'):
    raise RuntimeError('This application requires PostgreSQL')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5,
                       pool_timeout=10, connect_args={'connect_timeout':10})
Session = sessionmaker(engine, expire_on_commit=False)
