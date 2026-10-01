from __future__ import annotations

_SCHEMA_VERSION = 2
_TABLES = {
    "projects",
    "source_events",
    "live_inputs",
    "authorization_uses",
    "source_attributions",
    "tool_receipts",
    "reviews",
    "corrections",
    "claim_revisions",
}
_DDL = (
    "CREATE TABLE projects (project TEXT PRIMARY KEY, "
    "revision INTEGER NOT NULL CHECK(revision >= 0))",
    """CREATE TABLE source_events (
        source_id TEXT PRIMARY KEY, project TEXT NOT NULL, speaker TEXT NOT NULL,
        said_at TEXT, recorded_at TEXT NOT NULL, exact_text TEXT NOT NULL,
        sha256 TEXT NOT NULL, source_type TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE live_inputs (
        source_id TEXT PRIMARY KEY REFERENCES source_events(source_id),
        subject_id TEXT NOT NULL, intent_json TEXT)""",
    """CREATE TABLE authorization_uses (
        live_user_source_id TEXT PRIMARY KEY REFERENCES source_events(source_id),
        authorization_sha256 TEXT NOT NULL, project TEXT NOT NULL, action TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE source_attributions (
        source_id TEXT PRIMARY KEY REFERENCES source_events(source_id), project TEXT NOT NULL,
        authorization_json TEXT NOT NULL, recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE tool_receipts (
        tool_receipt_id TEXT PRIMARY KEY, source_id TEXT UNIQUE NOT NULL
        REFERENCES source_events(source_id),
        project TEXT NOT NULL, tool_name TEXT NOT NULL, operation TEXT NOT NULL,
        input_sha256 TEXT NOT NULL, result_json TEXT NOT NULL, result_sha256 TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE reviews (
        review_id TEXT PRIMARY KEY, project TEXT NOT NULL, source_id TEXT NOT NULL,
        review_json TEXT NOT NULL, review_sha256 TEXT NOT NULL, facts_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE corrections (
        correction_id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(review_id),
        project TEXT NOT NULL, operation TEXT NOT NULL, correction_json TEXT NOT NULL,
        state_json TEXT NOT NULL, authorization_json TEXT NOT NULL,
        supersessions_json TEXT NOT NULL,
        recorded_at TEXT NOT NULL, revision INTEGER NOT NULL)""",
    """CREATE TABLE claim_revisions (
        revision_id TEXT PRIMARY KEY, project TEXT NOT NULL, fact_key TEXT NOT NULL,
        evidence_ids_json TEXT NOT NULL, state TEXT NOT NULL, kind TEXT NOT NULL,
        payload_json TEXT NOT NULL, event_time TEXT, recorded_at TEXT NOT NULL,
        authorization_json TEXT, tool_receipt_id TEXT REFERENCES tool_receipts(tool_receipt_id),
        related_fact_key TEXT, payload_sha256 TEXT NOT NULL, revision INTEGER NOT NULL)""",
    "CREATE INDEX claim_revisions_project_fact ON claim_revisions(project, fact_key, revision)",
    "CREATE INDEX corrections_review_revision ON corrections(review_id, revision)",
)
_IMMUTABLE_TABLES = _TABLES - {"projects"}
_COLUMNS = {
    "projects": ("project", "revision"),
    "source_events": (
        "source_id",
        "project",
        "speaker",
        "said_at",
        "recorded_at",
        "exact_text",
        "sha256",
        "source_type",
        "revision",
    ),
    "live_inputs": ("source_id", "subject_id", "intent_json"),
    "authorization_uses": (
        "live_user_source_id",
        "authorization_sha256",
        "project",
        "action",
        "recorded_at",
        "revision",
    ),
    "source_attributions": (
        "source_id",
        "project",
        "authorization_json",
        "recorded_at",
        "revision",
    ),
    "tool_receipts": (
        "tool_receipt_id",
        "source_id",
        "project",
        "tool_name",
        "operation",
        "input_sha256",
        "result_json",
        "result_sha256",
        "recorded_at",
        "revision",
    ),
    "reviews": (
        "review_id",
        "project",
        "source_id",
        "review_json",
        "review_sha256",
        "facts_json",
        "recorded_at",
        "revision",
    ),
    "corrections": (
        "correction_id",
        "review_id",
        "project",
        "operation",
        "correction_json",
        "state_json",
        "authorization_json",
        "supersessions_json",
        "recorded_at",
        "revision",
    ),
    "claim_revisions": (
        "revision_id",
        "project",
        "fact_key",
        "evidence_ids_json",
        "state",
        "kind",
        "payload_json",
        "event_time",
        "recorded_at",
        "authorization_json",
        "tool_receipt_id",
        "related_fact_key",
        "payload_sha256",
        "revision",
    ),
}
