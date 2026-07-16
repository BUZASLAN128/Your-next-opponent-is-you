\set ON_ERROR_STOP on

\if :{?runtime_role}
\else
  \echo 'Pass -v runtime_role=<existing_non_superuser_role>.'
  \quit
\endif

GRANT CONNECT ON DATABASE :"DBNAME" TO :"runtime_role";
GRANT USAGE ON SCHEMA ynoy TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ynoy TO :"runtime_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ynoy TO :"runtime_role";

REVOKE INSERT, UPDATE, DELETE, TRUNCATE
    ON ynoy.schema_migrations FROM :"runtime_role";
REVOKE UPDATE, DELETE, TRUNCATE
    ON ynoy.audit_receipts FROM :"runtime_role";
