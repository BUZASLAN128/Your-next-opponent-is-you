CREATE TABLE IF NOT EXISTS ynoy.codex_ingestion_checkpoints (
    snapshot_id uuid NOT NULL,
    source_key text NOT NULL,
    blob_sha256 text NOT NULL REFERENCES ynoy.corpus_blobs(blob_sha256),
    expected_bytes bigint NOT NULL CHECK (expected_bytes >= 0),
    next_byte_offset bigint NOT NULL DEFAULT 0 CHECK (next_byte_offset >= 0),
    completed_lines bigint NOT NULL DEFAULT 0 CHECK (completed_lines >= 0),
    parser_state jsonb NOT NULL DEFAULT '{}'::jsonb,
    event_count bigint NOT NULL DEFAULT 0 CHECK (event_count >= 0),
    dialogue_count bigint NOT NULL DEFAULT 0 CHECK (dialogue_count >= 0),
    safe_action_count bigint NOT NULL DEFAULT 0 CHECK (safe_action_count >= 0),
    quarantined_count bigint NOT NULL DEFAULT 0 CHECK (quarantined_count >= 0),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'complete')),
    parser_version text NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (snapshot_id, source_key),
    FOREIGN KEY (snapshot_id, source_key)
        REFERENCES ynoy.corpus_snapshot_files(snapshot_id, source_key) ON DELETE CASCADE,
    CHECK (next_byte_offset <= expected_bytes),
    CHECK ((status = 'complete') = (next_byte_offset = expected_bytes)),
    CHECK (event_count = dialogue_count + safe_action_count + quarantined_count)
);

CREATE TABLE IF NOT EXISTS ynoy.codex_normalized_events (
    record_id uuid PRIMARY KEY,
    snapshot_id uuid NOT NULL,
    source_key text NOT NULL,
    blob_sha256 text NOT NULL,
    byte_start bigint NOT NULL CHECK (byte_start >= 0),
    byte_length bigint NOT NULL CHECK (byte_length > 0),
    line_number bigint NOT NULL CHECK (line_number > 0),
    record_sha256 text NOT NULL,
    record_type text NOT NULL,
    payload_type text,
    actor_origin text NOT NULL,
    structural_role text NOT NULL,
    claim_holder text NOT NULL,
    source_authority text NOT NULL,
    status text NOT NULL CHECK (status IN ('dialogue', 'safe_action', 'quarantined')),
    content text,
    content_sha256 text,
    event_time timestamptz,
    conversation_key text,
    turn_key text,
    duplicate_of uuid,
    exclusion_reason text,
    safe_action_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_class text NOT NULL CHECK (data_class IN ('D0', 'D2')),
    synthetic boolean NOT NULL,
    parser_version text NOT NULL,
    event_sha256 text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    FOREIGN KEY (snapshot_id, source_key)
        REFERENCES ynoy.codex_ingestion_checkpoints(snapshot_id, source_key)
        ON DELETE CASCADE,
    CHECK ((status = 'dialogue') = (content IS NOT NULL AND content_sha256 IS NOT NULL)),
    CHECK ((status = 'safe_action') = (safe_action_metadata <> '{}'::jsonb)),
    CHECK ((status = 'quarantined') = (exclusion_reason IS NOT NULL)),
    CHECK (synthetic = (data_class = 'D0')),
    UNIQUE (snapshot_id, source_key, byte_start)
);

CREATE INDEX IF NOT EXISTS ix_codex_normalized_events_dialogue
    ON ynoy.codex_normalized_events(snapshot_id, event_time)
    WHERE status = 'dialogue';

CREATE TABLE IF NOT EXISTS ynoy.codex_ingestion_receipts (
    record_id uuid PRIMARY KEY,
    snapshot_id uuid NOT NULL REFERENCES ynoy.corpus_snapshots(snapshot_id) ON DELETE CASCADE,
    snapshot_receipt_sha256 text NOT NULL,
    receipt_sha256 text NOT NULL UNIQUE,
    status text NOT NULL CHECK (status IN ('complete', 'partial')),
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE OR REPLACE FUNCTION ynoy.reject_ingestion_receipt_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'ingestion receipts are immutable';
END;
$$;

DROP TRIGGER IF EXISTS codex_ingestion_receipts_no_update
    ON ynoy.codex_ingestion_receipts;
CREATE TRIGGER codex_ingestion_receipts_no_update
BEFORE UPDATE ON ynoy.codex_ingestion_receipts
FOR EACH ROW EXECUTE FUNCTION ynoy.reject_ingestion_receipt_update();
