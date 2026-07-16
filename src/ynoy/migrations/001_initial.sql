CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ynoy.inventory_manifests (
    record_id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL,
    source_archive_sha256 text NOT NULL,
    manifest_sha256 text NOT NULL UNIQUE,
    source_data_class text NOT NULL CHECK (source_data_class IN ('D0', 'D1', 'D2', 'D3', 'D4', 'D5')),
    synthetic boolean NOT NULL,
    record jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.ingestion_approvals (
    record_id uuid PRIMARY KEY,
    manifest_id uuid NOT NULL REFERENCES ynoy.inventory_manifests(record_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL,
    approval_sha256 text NOT NULL UNIQUE,
    record jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.source_events (
    record_id uuid PRIMARY KEY,
    import_run_id uuid NOT NULL,
    source_id text NOT NULL,
    source_locator text NOT NULL,
    conversation_id text NOT NULL,
    branch_id text NOT NULL,
    event_id text NOT NULL,
    parent_event_id text,
    speaker text NOT NULL CHECK (speaker IN ('user', 'assistant', 'system', 'tool', 'third_party', 'unknown')),
    claim_holder text NOT NULL CHECK (claim_holder IN ('represented_user', 'assistant', 'third_party', 'unknown')),
    source_authority text NOT NULL,
    data_class text NOT NULL CHECK (data_class IN ('D0', 'D1', 'D2', 'D3', 'D4', 'D5')),
    event_time timestamptz,
    content text NOT NULL,
    content_sha256 text NOT NULL,
    origin_cluster_id text NOT NULL,
    scope jsonb NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (source_id, event_id)
);

CREATE INDEX IF NOT EXISTS ix_source_events_import_run
    ON ynoy.source_events(import_run_id);
CREATE INDEX IF NOT EXISTS ix_source_events_subject_scope
    ON ynoy.source_events((scope ->> 'person_id'), conversation_id, event_time);
CREATE INDEX IF NOT EXISTS ix_source_events_origin_cluster
    ON ynoy.source_events(origin_cluster_id);

CREATE TABLE IF NOT EXISTS ynoy.source_receipts (
    record_id uuid PRIMARY KEY,
    import_run_id uuid NOT NULL UNIQUE,
    source_id text NOT NULL,
    source_archive_sha256 text NOT NULL,
    status text NOT NULL CHECK (status IN ('complete', 'partial', 'rejected')),
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.bootstrap_declarations (
    record_id uuid PRIMARY KEY,
    subject_id text NOT NULL,
    kind text NOT NULL,
    statement text NOT NULL,
    scope jsonb NOT NULL,
    decision_label text,
    source_name text NOT NULL,
    data_class text NOT NULL CHECK (data_class IN ('D0', 'D3')),
    synthetic boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('confirmed', 'superseded', 'invalidated')),
    superseded_by uuid,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_bootstrap_subject_status
    ON ynoy.bootstrap_declarations(subject_id, status, created_at);

CREATE TABLE IF NOT EXISTS ynoy.claim_candidates (
    record_id uuid PRIMARY KEY,
    subject_id text NOT NULL,
    claim_holder text NOT NULL,
    kind text NOT NULL,
    proposition text NOT NULL,
    scope jsonb NOT NULL,
    confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status text NOT NULL CHECK (status IN ('proposed', 'confirmed', 'disputed', 'superseded', 'invalidated')),
    valid_from timestamptz,
    valid_until timestamptz,
    origin_cluster_ids text[] NOT NULL,
    revision_of uuid,
    superseded_by uuid,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_claim_subject_status
    ON ynoy.claim_candidates(subject_id, status, kind);

CREATE TABLE IF NOT EXISTS ynoy.decision_events (
    record_id uuid PRIMARY KEY,
    subject_id text NOT NULL,
    source_event_id uuid NOT NULL REFERENCES ynoy.source_events(record_id) ON DELETE CASCADE,
    label text NOT NULL,
    target_locator text,
    rationale text,
    rationale_is_inferred boolean NOT NULL,
    demanded_evidence text[] NOT NULL,
    scope jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.identity_candidates (
    record_id uuid PRIMARY KEY,
    subject_id text NOT NULL,
    view text NOT NULL CHECK (view IN ('trait', 'value', 'narrative', 'metacognition')),
    proposition text NOT NULL,
    confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status text NOT NULL CHECK (status IN ('proposed', 'confirmed', 'disputed', 'superseded', 'invalidated')),
    scope jsonb NOT NULL,
    origin_cluster_ids text[] NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.identity_embeddings (
    record_id uuid PRIMARY KEY REFERENCES ynoy.identity_candidates(record_id) ON DELETE CASCADE,
    model_id text NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.continuity_events (
    record_id uuid PRIMARY KEY,
    subject_id text NOT NULL,
    event_type text NOT NULL,
    earlier_record_id uuid NOT NULL,
    later_record_id uuid NOT NULL,
    explanation text,
    effective_at timestamptz,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.derivation_edges (
    record_id uuid PRIMARY KEY,
    source_record_id uuid NOT NULL,
    derived_record_id uuid NOT NULL,
    relation text NOT NULL,
    origin_cluster_id text NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (source_record_id, derived_record_id, relation)
);

CREATE INDEX IF NOT EXISTS ix_derivation_source
    ON ynoy.derivation_edges(source_record_id);
CREATE INDEX IF NOT EXISTS ix_derivation_derived
    ON ynoy.derivation_edges(derived_record_id);

CREATE TABLE IF NOT EXISTS ynoy.control_records (
    record_id uuid PRIMARY KEY,
    subject_id text NOT NULL,
    instruction text NOT NULL,
    scope jsonb NOT NULL,
    authority text NOT NULL CHECK (authority IN ('remember', 'predict', 'recommend', 'review')),
    status text NOT NULL,
    source_event_id uuid NOT NULL REFERENCES ynoy.source_events(record_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.memory_corrections (
    record_id uuid PRIMARY KEY,
    target_record_id uuid NOT NULL,
    replacement_record_id uuid,
    reason text NOT NULL,
    subject_id text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.benchmark_cases (
    record_id uuid PRIMARY KEY,
    case_id text NOT NULL UNIQUE,
    event_time timestamptz NOT NULL,
    dependency_cluster_id text NOT NULL,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.benchmark_manifests (
    record_id uuid PRIMARY KEY,
    manifest_sha256 text NOT NULL UNIQUE,
    record jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.benchmark_runs (
    record_id uuid PRIMARY KEY,
    manifest_id uuid NOT NULL REFERENCES ynoy.benchmark_manifests(record_id),
    manifest_sha256 text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'complete', 'invalid')),
    config jsonb NOT NULL,
    metrics jsonb,
    fatal_gates text[] NOT NULL DEFAULT '{}',
    started_at timestamptz NOT NULL,
    completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS ynoy.benchmark_predictions (
    run_id uuid NOT NULL REFERENCES ynoy.benchmark_runs(record_id) ON DELETE CASCADE,
    case_id text NOT NULL,
    algorithm text NOT NULL,
    regime text NOT NULL,
    prediction jsonb NOT NULL,
    PRIMARY KEY (run_id, case_id, algorithm, regime)
);

CREATE TABLE IF NOT EXISTS ynoy.private_reports (
    record_id uuid PRIMARY KEY,
    artifact_name text NOT NULL,
    report_type text NOT NULL,
    status text NOT NULL CHECK (status IN ('current', 'stale', 'invalidated')),
    source_record_ids uuid[] NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.erasure_plans (
    record_id uuid PRIMARY KEY,
    source_id text NOT NULL,
    target_record_ids uuid[] NOT NULL,
    target_counts jsonb NOT NULL,
    plan_sha256 text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    confirmed_at timestamptz,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS ynoy.audit_receipts (
    sequence_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_id uuid NOT NULL UNIQUE,
    event_type text NOT NULL,
    actor_class text NOT NULL,
    policy_version text NOT NULL,
    parser_version text,
    config_version text NOT NULL,
    opaque_input_ids text[] NOT NULL,
    input_count integer NOT NULL CHECK (input_count >= 0),
    data_classes text[] NOT NULL,
    decision text NOT NULL,
    reason_code text NOT NULL,
    destination text,
    retention_class text,
    artifact_id text,
    status text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE OR REPLACE FUNCTION ynoy.reject_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit receipts are append-only';
END;
$$;

DROP TRIGGER IF EXISTS audit_receipts_append_only ON ynoy.audit_receipts;
CREATE TRIGGER audit_receipts_append_only
BEFORE UPDATE OR DELETE ON ynoy.audit_receipts
FOR EACH ROW EXECUTE FUNCTION ynoy.reject_audit_mutation();
