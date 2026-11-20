from pathlib import Path
from sqlalchemy.schema import CreateTable,CreateIndex
from sqlalchemy.dialects import postgresql
from app.models.entities import Base
statements=[]
for table in Base.metadata.sorted_tables:
    statements.append(str(CreateTable(table).compile(dialect=postgresql.dialect())))
    statements.extend(str(CreateIndex(idx).compile(dialect=postgresql.dialect())) for idx in table.indexes)
source='''"""Frozen initial PostgreSQL schema for local U8 import platform."""
from alembic import op
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
'''
source+='\nSTATEMENTS = '+repr(statements)+'\n\ndef upgrade():\n    for sql in STATEMENTS: op.execute(sql)\n\ndef downgrade():\n'
for table in reversed(Base.metadata.sorted_tables):source+=f'    op.drop_table({table.name!r})\n'
Path('migrations/versions/0001_initial.py').write_text(source,encoding='utf8')
