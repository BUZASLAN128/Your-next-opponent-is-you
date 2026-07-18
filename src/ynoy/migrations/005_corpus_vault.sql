CREATE TABLE IF NOT EXISTS ynoy.codex_corpus_approvals (
    record_id uuid PRIMARY KEY,
    manifest_id uuid NOT NULL,
    manifest_sha256 text NOT NULL,
    approval_sha256 text NOT NULL UNIQUE,
    allowed_operations text[] NOT NULL,
    third_party_reviewed boolean NOT NULL,
    synthetic boolean NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.corpus_snapshots (
    snapshot_id uuid PRIMARY KEY,
    manifest_id uuid NOT NULL,
    manifest_sha256 text NOT NULL,
    approval_id uuid NOT NULL
        REFERENCES ynoy.codex_corpus_approvals(record_id) ON DELETE CASCADE,
    latest_receipt_id uuid NOT NULL UNIQUE,
    source_data_class text NOT NULL CHECK (source_data_class IN ('D0', 'D2')),
    synthetic boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('complete', 'partial', 'failed')),
    expected_file_count integer NOT NULL CHECK (expected_file_count >= 0),
    expected_bytes bigint NOT NULL CHECK (expected_bytes >= 0),
    vaulted_file_count integer NOT NULL CHECK (vaulted_file_count >= 0),
    vaulted_bytes bigint NOT NULL CHECK (vaulted_bytes >= 0),
    deferred_file_count integer NOT NULL CHECK (deferred_file_count >= 0),
    error_file_count integer NOT NULL CHECK (error_file_count >= 0),
    updated_at timestamptz NOT NULL,
    CHECK (synthetic = (source_data_class = 'D0'))
);

CREATE TABLE IF NOT EXISTS ynoy.corpus_snapshot_receipts (
    record_id uuid PRIMARY KEY,
    snapshot_id uuid NOT NULL
        REFERENCES ynoy.corpus_snapshots(snapshot_id) ON DELETE CASCADE,
    previous_receipt_sha256 text,
    receipt_sha256 text NOT NULL UNIQUE,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.corpus_blobs (
    blob_sha256 text PRIMARY KEY,
    byte_count bigint NOT NULL CHECK (byte_count >= 0),
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.corpus_snapshot_files (
    snapshot_id uuid NOT NULL
        REFERENCES ynoy.corpus_snapshots(snapshot_id) ON DELETE CASCADE,
    source_key text NOT NULL,
    partition text NOT NULL CHECK (partition IN ('sessions', 'archived_sessions')),
    expected_bytes bigint NOT NULL CHECK (expected_bytes >= 0),
    status text NOT NULL CHECK (
        status IN ('vaulted', 'deferred_unstable', 'deferred_rollout', 'error')
    ),
    blob_sha256 text REFERENCES ynoy.corpus_blobs(blob_sha256),
    vaulted_bytes bigint NOT NULL CHECK (vaulted_bytes >= 0),
    error_code text,
    PRIMARY KEY (snapshot_id, source_key),
    CHECK ((status = 'vaulted') = (blob_sha256 IS NOT NULL)),
    CHECK ((status = 'error') = (error_code IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS ix_corpus_snapshot_files_blob
    ON ynoy.corpus_snapshot_files(blob_sha256) WHERE blob_sha256 IS NOT NULL;

CREATE OR REPLACE FUNCTION ynoy.reject_snapshot_receipt_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'snapshot receipts are immutable';
END;
$$;

DROP TRIGGER IF EXISTS corpus_snapshot_receipts_no_update
    ON ynoy.corpus_snapshot_receipts;
CREATE TRIGGER corpus_snapshot_receipts_no_update
BEFORE UPDATE ON ynoy.corpus_snapshot_receipts
FOR EACH ROW EXECUTE FUNCTION ynoy.reject_snapshot_receipt_update();
