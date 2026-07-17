CREATE TABLE IF NOT EXISTS ynoy.canonical_claims (
    record_id uuid PRIMARY KEY,
    subject_id text NOT NULL,
    claim_holder text NOT NULL CHECK (claim_holder = 'represented_user'),
    source_authority text NOT NULL CHECK (source_authority = 'explicit_user_statement'),
    explicit_user_adoption boolean NOT NULL CHECK (explicit_user_adoption),
    claim_type text NOT NULL,
    target_layer text NOT NULL,
    literal_statement text NOT NULL,
    interpretation text,
    candidate_consequence text,
    persona_kind text,
    persona_stratum text,
    scope jsonb NOT NULL,
    decision_label text,
    status text NOT NULL CHECK (status IN ('confirmed', 'superseded', 'invalidated')),
    data_class text NOT NULL CHECK (data_class IN ('D0', 'D3')),
    synthetic boolean NOT NULL,
    admission_receipt_id uuid NOT NULL UNIQUE,
    source_link_ids uuid[] NOT NULL CHECK (cardinality(source_link_ids) > 0),
    supersedes_claim_id uuid,
    superseded_by uuid,
    claim_sha256 text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    CHECK (synthetic = (data_class = 'D0')),
    CHECK ((target_layer = 'persona_candidate') =
           (persona_kind IS NOT NULL AND persona_stratum IS NOT NULL)),
    CHECK (supersedes_claim_id IS NULL OR supersedes_claim_id <> record_id),
    CHECK (superseded_by IS NULL OR superseded_by <> record_id)
);

CREATE INDEX IF NOT EXISTS ix_canonical_claim_subject_status
    ON ynoy.canonical_claims(subject_id, data_class, status, target_layer, created_at);

CREATE TABLE IF NOT EXISTS ynoy.claim_admission_receipts (
    record_id uuid PRIMARY KEY,
    claim_id uuid NOT NULL UNIQUE
        REFERENCES ynoy.canonical_claims(record_id) ON DELETE CASCADE,
    subject_id text NOT NULL,
    actor text NOT NULL CHECK (actor = 'user'),
    claim_holder text NOT NULL CHECK (claim_holder = 'represented_user'),
    source_authority text NOT NULL CHECK (source_authority = 'explicit_user_statement'),
    explicit_adoption boolean NOT NULL CHECK (explicit_adoption),
    adoption_action text NOT NULL CHECK (adoption_action NOT IN ('reject', 'propose_for_core')),
    adoption_receipt_id uuid NOT NULL,
    adoption_receipt_sha256 text NOT NULL,
    review_sha256 text NOT NULL,
    reviewed_state_sha256 text NOT NULL,
    claim_sha256 text NOT NULL,
    source_link_ids uuid[] NOT NULL CHECK (cardinality(source_link_ids) > 0),
    source_count integer NOT NULL CHECK (source_count = cardinality(source_link_ids)),
    data_class text NOT NULL CHECK (data_class IN ('D0', 'D3')),
    supersedes_claim_id uuid,
    receipt_sha256 text NOT NULL UNIQUE,
    authority text NOT NULL CHECK (authority = 'none'),
    automatic_core_promotion boolean NOT NULL CHECK (NOT automatic_core_promotion),
    created_at timestamptz NOT NULL
);

CREATE OR REPLACE FUNCTION ynoy.reject_claim_admission_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'claim admission receipts are immutable';
END;
$$;

DROP TRIGGER IF EXISTS claim_admission_receipts_no_update
    ON ynoy.claim_admission_receipts;
CREATE TRIGGER claim_admission_receipts_no_update
BEFORE UPDATE ON ynoy.claim_admission_receipts
FOR EACH ROW EXECUTE FUNCTION ynoy.reject_claim_admission_update();
