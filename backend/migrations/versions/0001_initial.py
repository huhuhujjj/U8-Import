"""Frozen initial PostgreSQL schema for local U8 import platform."""
from alembic import op
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

STATEMENTS = ['\nCREATE TABLE field_mappings (\n\tbusiness_type VARCHAR NOT NULL, \n\ttemplate_name VARCHAR NOT NULL, \n\tsource_field VARCHAR NOT NULL, \n\ttarget_field VARCHAR NOT NULL, \n\tenabled BOOLEAN NOT NULL, \n\tversion INTEGER NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (template_name, version, target_field)\n)\n\n', '\nCREATE TABLE import_jobs (\n\tbusiness_type VARCHAR NOT NULL, \n\tfile_name VARCHAR NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\ttotal_count INTEGER NOT NULL, \n\tvalid_count INTEGER NOT NULL, \n\tsuccess_count INTEGER NOT NULL, \n\tfailed_count INTEGER NOT NULL, \n\tskipped_count INTEGER NOT NULL, \n\theader JSONB NOT NULL, \n\tmapping JSONB NOT NULL, \n\tpayload_hash VARCHAR NOT NULL, \n\torder_key VARCHAR NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n', 'CREATE INDEX ix_import_jobs_order_key ON import_jobs (order_key)', '\nCREATE TABLE mock_u8_orders (\n\torder_key VARCHAR NOT NULL, \n\tpayload JSONB NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (order_key)\n)\n\n', '\nCREATE TABLE audit_logs (\n\tjob_id VARCHAR(36), \n\taction VARCHAR NOT NULL, \n\toperator VARCHAR NOT NULL, \n\tdetails JSONB NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(job_id) REFERENCES import_jobs (id)\n)\n\n', '\nCREATE TABLE import_rows (\n\tjob_id VARCHAR(36) NOT NULL, \n\tsource_row INTEGER NOT NULL, \n\tline_reference VARCHAR NOT NULL, \n\traw_data JSONB NOT NULL, \n\tnormalized_data JSONB NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tbusiness_key VARCHAR NOT NULL, \n\tretry_count INTEGER NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (job_id, line_reference), \n\tFOREIGN KEY(job_id) REFERENCES import_jobs (id)\n)\n\n', 'CREATE INDEX ix_import_rows_job_id ON import_rows (job_id)', 'CREATE INDEX ix_import_rows_business_key ON import_rows (business_key)', '\nCREATE TABLE order_executions (\n\torder_key VARCHAR NOT NULL, \n\tpayload_hash VARCHAR NOT NULL, \n\tjob_id VARCHAR(36) NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\terp_business_id VARCHAR, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (order_key), \n\tFOREIGN KEY(job_id) REFERENCES import_jobs (id)\n)\n\n', '\nCREATE TABLE erp_results (\n\tjob_id VARCHAR(36) NOT NULL, \n\trow_id VARCHAR(36) NOT NULL, \n\trequest_data JSONB NOT NULL, \n\tresponse_data JSONB NOT NULL, \n\terp_business_id VARCHAR, \n\tstatus VARCHAR NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(job_id) REFERENCES import_jobs (id), \n\tFOREIGN KEY(row_id) REFERENCES import_rows (id)\n)\n\n', 'CREATE INDEX ix_erp_results_job_id ON erp_results (job_id)', '\nCREATE TABLE import_errors (\n\tjob_id VARCHAR(36) NOT NULL, \n\trow_id VARCHAR(36), \n\terror_type VARCHAR NOT NULL, \n\terror_code VARCHAR NOT NULL, \n\terror_message VARCHAR NOT NULL, \n\tid VARCHAR(36) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(job_id) REFERENCES import_jobs (id), \n\tFOREIGN KEY(row_id) REFERENCES import_rows (id)\n)\n\n', 'CREATE INDEX ix_import_errors_job_id ON import_errors (job_id)']

def upgrade():
    for sql in STATEMENTS: op.execute(sql)

def downgrade():
    op.drop_table('import_errors')
    op.drop_table('erp_results')
    op.drop_table('order_executions')
    op.drop_table('import_rows')
    op.drop_table('audit_logs')
    op.drop_table('mock_u8_orders')
    op.drop_table('import_jobs')
    op.drop_table('field_mappings')
