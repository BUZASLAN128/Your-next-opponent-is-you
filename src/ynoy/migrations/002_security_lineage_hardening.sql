DROP TRIGGER IF EXISTS audit_receipts_no_truncate ON ynoy.audit_receipts;
CREATE TRIGGER audit_receipts_no_truncate
BEFORE TRUNCATE ON ynoy.audit_receipts
FOR EACH STATEMENT EXECUTE FUNCTION ynoy.reject_audit_mutation();

CREATE TABLE IF NOT EXISTS ynoy.bootstrap_sources (
    record_id uuid PRIMARY KEY,
    source_name text NOT NULL,
    data_class text NOT NULL CHECK (data_class IN ('D0', 'D3')),
    synthetic boolean NOT NULL,
    created_at timestamptz NOT NULL
);

ALTER TABLE ynoy.bootstrap_declarations
    ADD COLUMN IF NOT EXISTS source_record_id uuid
    REFERENCES ynoy.bootstrap_sources(record_id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS ix_bootstrap_source
    ON ynoy.bootstrap_declarations(source_record_id);
