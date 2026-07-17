CREATE TABLE IF NOT EXISTS ynoy.claim_source_links (
    record_id uuid PRIMARY KEY,
    claim_id uuid NOT NULL REFERENCES ynoy.canonical_claims(record_id) ON DELETE CASCADE,
    source_receipt_id uuid NOT NULL,
    subject_id text NOT NULL,
    source_data_class text NOT NULL CHECK (source_data_class IN ('D0', 'D2')),
    source_response_sha256 text NOT NULL,
    character_start integer NOT NULL CHECK (character_start >= 0),
    character_end integer NOT NULL CHECK (character_end > character_start),
    span_text_sha256 text NOT NULL,
    origin_cluster_id text NOT NULL,
    link_sha256 text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    UNIQUE (claim_id, source_receipt_id, character_start, character_end)
);

CREATE INDEX IF NOT EXISTS ix_claim_source_receipt
    ON ynoy.claim_source_links(source_receipt_id, claim_id);
CREATE INDEX IF NOT EXISTS ix_claim_source_origin_cluster
    ON ynoy.claim_source_links(origin_cluster_id);
