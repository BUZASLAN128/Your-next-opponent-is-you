\set ON_ERROR_STOP on

\if :{?runtime_role}
\else
  \echo 'Pass -v runtime_role=<existing_non_superuser_role>.'
  \quit
\endif

GRANT CONNECT ON DATABASE :"DBNAME" TO :"runtime_role";
GRANT USAGE ON SCHEMA ynoy TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    ynoy.inventory_manifests,
    ynoy.ingestion_approvals,
    ynoy.source_events,
    ynoy.source_receipts,
    ynoy.bootstrap_sources,
    ynoy.bootstrap_declarations,
    ynoy.claim_candidates,
    ynoy.decision_events,
    ynoy.identity_candidates,
    ynoy.identity_embeddings,
    ynoy.continuity_events,
    ynoy.derivation_edges,
    ynoy.control_records,
    ynoy.memory_corrections,
    ynoy.benchmark_cases,
    ynoy.benchmark_manifests,
    ynoy.benchmark_runs,
    ynoy.benchmark_predictions,
    ynoy.private_reports,
    ynoy.erasure_plans
    TO :"runtime_role";
GRANT SELECT, INSERT ON TABLE ynoy.audit_receipts TO :"runtime_role";
GRANT SELECT ON TABLE ynoy.schema_migrations TO :"runtime_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ynoy TO :"runtime_role";

REVOKE UPDATE, DELETE, TRUNCATE ON TABLE ynoy.audit_receipts FROM :"runtime_role";
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE ynoy.schema_migrations FROM :"runtime_role";
