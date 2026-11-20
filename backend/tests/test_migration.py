import uuid,importlib.util
from pathlib import Path
from sqlalchemy import text,create_engine,inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.session import engine

def test_frozen_migration_creates_expected_tables():
    schema='migration_test_'+uuid.uuid4().hex
    with engine.begin() as conn:conn.execute(text(f'CREATE SCHEMA {schema}'))
    scoped=create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        spec=importlib.util.spec_from_file_location('initial',Path(__file__).resolve().parents[1]/'migrations/versions/0001_initial.py')
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with scoped.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):migration.upgrade()
            assert set(inspect(conn).get_table_names(schema=schema))=={'import_jobs','import_rows','import_errors','erp_results','field_mappings','audit_logs','order_executions','mock_u8_orders'}
            for name in ('0002_u8_remote_state','0003_mapping_headers','0004_operations'):
                spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/'migrations/versions'/f'{name}.py')
                next_migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(next_migration)
                with Operations.context(MigrationContext.configure(conn)):next_migration.upgrade()
            assert {'queue_tasks','worker_heartbeats'}<=set(inspect(conn).get_table_names(schema=schema))
            assert 'source_headers' in {c['name'] for c in inspect(conn).get_columns('field_mappings')}
    finally:
        scoped.dispose()
        with engine.begin() as conn:conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
