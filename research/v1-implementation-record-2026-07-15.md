# V1 Scientific-Core Implementation Record

> Date: 2026-07-15
> Status: implemented prototype; synthetic validation only
> Authority: repository source, local runtime observations, and explicit user
> decisions recorded in D-025 through D-033
>
> Update: the later deterministic formal-runtime checkpoint is recorded in
> [V1.8 Formal Runtime Conformance Record](v1-8-runtime-record-2026-07-18.md).
> That record supersedes this file's test counts and formal-safety status, but
> not its historical V1 scope or scientific limitations.

## Objective

Turn the technology-neutral research model into the smallest falsifiable
product slice: a local-first command-line harness that can test whether a
structured, scoped representation of a user's coding judgments predicts later
judgments better than simpler baselines.

This implementation is not evidence that a faithful persona has been built.
It creates the contracts and experimental machinery needed to test that claim.

## Confirmed V1 Boundary

- The first measurable slice is coding judgment in **Mirror** mode.
- Python 3.12 is the application runtime.
- PostgreSQL 18.4 plus pgvector 0.8.2 is the local record store.
- Provenance and dependency relationships use explicit SQL edge tables; V1
  does not add a separate graph database or GraphRAG framework.
- Docker Compose provides the local database runtime.
- AGPL-3.0-only is the repository license for this implementation.
- Real raw and derived identity data remains outside every Git worktree.
- External reasoners receive D0 public or synthetic material only. D1 through
  D5 are blocked before adapter invocation.
- No candidate is promoted into the durable core automatically in V1.
- The data-free Manager's generated operating seed is system control, not
  persona evidence, and is never persisted.
- The first persona surface is an explicitly adopted, declared-only,
  non-persisting preview with unvalidated confidence and no generalization.
- Mirror predicts and Advisor proposes; neither mode may send, execute, or
  claim an external action occurred.
- canonical output always says `action_status=not_performed`, keeps authority
  at none and the action receipt null, and tags reasoner text as
  `untrusted_reasoner_advisory`; fixed local guidance is `system_advisory`.

## Implemented Shape

The public repository now contains these responsibility boundaries:

1. `corpus`: bounded ZIP inventory, explicit approval, source-preserving
   ChatGPT-export parsing, and synthetic-fixture validation;
2. `models`: typed source, memory, benchmark, scope, authority, and output
   contracts;
3. `storage`: PostgreSQL repositories for corpus, memory, benchmark, audit,
   and erasure operations;
4. `policy`: public/private path, loopback database,
   data-class egress, and authority checks;
5. `reasoner` and `embeddings`: provider-neutral loopback-only adapters;
6. `benchmark`: dependency-cluster temporal splits, baselines, structured-core
   arm, metrics, frozen manifests, and private reports;
7. `manager`: a database-free, provider-free cold-start workspace with typed,
   non-personal operating memory;
8. `persona`: explicit-adoption parsing and a four-view plus scoped-object
   preview that never writes or promotes identity;
9. `cli`: JSON stdout envelopes and redacted stderr diagnostics;
10. `doctor`: readiness checks that distinguish synthetic from real-data use;
11. `scripts`: Markdown bundling and source-size enforcement.

The asset, trust-boundary, and adversarial acceptance details are recorded in
the [V1 threat model](v1-threat-model-2026-07-15.md).

The implementation deliberately avoids one central service object. Production
modules receive dependencies explicitly and are split by one main
responsibility.

## Data and Authority Contract

### Data classes

| Class | Meaning | V1 outbound policy |
| --- | --- | --- |
| D0 | Public or explicitly synthetic data | Allowed to a configured adapter |
| D1 | Private current-task material | Blocked |
| D2 | Raw conversation corpus | Blocked |
| D3 | Derived persona or behavioral profile | Blocked |
| D4 | Credential or secret | Blocked |
| D5 | Third-party personal data | Blocked |

### Source authority

The source record separates message speaker, represented claim holder, source
authority, scope, time, branch, and derivation origin. Assistant-authored text
cannot become represented-user evidence merely because it describes the user.
An unannotated `role=user` turn is stored as `user_turn_unattributed` with an
unknown claim holder: pasted mail, quoted text, and third-party reports do not
become persona evidence until an explicit span-level adoption or attribution
step exists. Imported instructions remain inert content.

### Persistence

Cold start is a supported state, not an error. Without history or declarations,
Mirror abstains and asks one high-value question; Advisor can provide generic
advice while declaring personal fit unknown. User-authored bootstrap material
was initially modeled as an explicit declaration rather than observed
behavior. Security review then established that the current persistence schema
does not retain speaker, claim holder, adoption, source authority, or identity-
interpretation plane. Real D3 bootstrap and replacement persistence are
therefore blocked with `real_identity_persistence_unsupported` until a separate
schema decision can preserve those fields and prove a storage round trip.
Synthetic D0 bootstrap remains available for apparatus tests. It cannot enter
a subject containing private identity evidence, and private evidence cannot
enter a D0 subject. Mutations take a transaction-scoped subject lock;
corrections must remain in the locked target's data class. Synthetic and real
inference reject contaminated legacy subjects, while stored D3 declarations
remain unreadable as persona evidence until adoption provenance is verifiable.
The public inference repository has no unbound default: callers must choose D0
or D3, and each read performs its own readiness check. Plane-filtered inspection
uses `inspect_*` methods on a separate type, so it cannot be passed to the core
inference protocol by structural typing. Subject advisory-lock contention uses
a non-blocking transaction lock and returns retryable `identity_subject_busy`,
rolling back the operation rather than permitting cross-batch lock cycles.

`manager start` now exposes the earlier cold-start behavior without requiring
PostgreSQL, a private root, or a reasoner. It auto-generates only a
deterministic D0 `system_control` seed. The output reports evidence regime
zero, empty persona memory, D1 current-task classification, no database or
provider use, no persistence, no audit write, no action, and no automatic core
promotion. Operating rules use a separate type from bootstrap declarations and
claim candidates, so they cannot be selected as represented-user evidence.

`persona preview` is the next non-persisting stage. Its source contract
requires `speaker=user`, `claim_holder=represented_user`, explicit adoption,
explicit-user source authority, the identity-interpretation plane, honest
synthetic classification, and matching subject/scope person. Real D3 files
must resolve inside the explicit private root and outside Git. The preview
preserves exact declarations, including their statement bytes, and receipts,
exposes empty candidate views,
reports `low_unvalidated`, and performs no database, provider, persistence,
action, authority, or core promotion. Free-form real Markdown is rejected
because it cannot yet preserve these per-item attribution fields.

Corrections create revision lineage. Erasure requires a short-lived plan hash,
removes dependent private records and artifacts, and leaves only a
content-free audit tombstone. Audit receipts are append-only and must not
become a second corpus. Protected database mutations and their audit receipts
commit in one transaction. Database guards reject audit `UPDATE`, `DELETE`,
and `TRUNCATE`; real-data commands also reject superuser or audit-mutating
runtime roles. Every data operation and doctor readiness additionally require
an exact name-and-digest match between packaged and applied migrations.

## Runtime Evidence

The following local observations were obtained on 2026-07-15:

- the pinned PostgreSQL/pgvector image built successfully from the exact
  pgvector source commit and verified archive digest;
- the container health check reported PostgreSQL `server_version_num=180004`;
- migrations `001_initial.sql` and `002_security_lineage_hardening.sql`
  completed against a loopback-only database;
- the database reported PostgreSQL 18.4 and pgvector 0.8.2;
- the runtime-role grant script was exercised with a disposable no-login role:
  it retained audit insert while superuser, audit update/delete/truncate, and
  migration insert privileges all remained false, then the role was removed;
- static source-limit, Ruff, strict mypy, and Python compilation gates were
  exercised during implementation;
- the final independent repository pytest run passed 139 tests
  with 75.04 percent measured branch coverage and the enforced 70 percent floor;
- the parent validation repeated the same 139 tests at 75.04
  percent, plus frozen dependency sync, Ruff, strict mypy over 56 source files,
  compilation, and source-modularity gates;
- twelve PostgreSQL-dependent integration/acceptance tests passed exact
  migration/version checks, update/delete/truncate-resistant audit, atomic
  mutation rollback, replay idempotency, explicit bootstrap correction,
  source/direct-record erasure lineage, restricted-role diagnosis, and
  resumable dependency erasure plus tombstone behavior;
- security regressions also passed DB URI/libpq-environment escape rejection,
  literal loopback host targeting, exact migration name/digest drift checks,
  branch-work budgets, adapter redirect/proxy/size/data-class boundaries, and
  canonical no-action output under adversarial reasoner text;
- the subprocess CLI acceptance passed inventory, approval, ingestion,
  bootstrap, Mirror, benchmark freeze/run/report, memory inspection, and
  erasure against explicitly synthetic data.
- after adding the data-free Manager slice, the complete repository gate
  passed 145 tests with 78.79 percent measured branch
  coverage, including PostgreSQL integration and synthetic acceptance; the six
  Manager-focused tests separately passed with database and
  network call spies remaining unused;
- frozen dependency sync, repository-wide Ruff, strict mypy over 60 source
  files, touched-file compilation, source modularity, and diff whitespace
  checks passed for the follow-up slice.
- after the declared-persona, benchmark-isolation, retrieval, provenance, and
  D0/private subject-plane follow-up, the final complete repository gate passed
  214 tests with 80.79 percent measured branch coverage. The focused persona
  and identity-boundary package passed 96 tests, including six loopback
  PostgreSQL identity-plane tests; the final public-reader and contention
  closure package passed 20 tests.
  Frozen dependency sync, repository-wide Ruff and format checks over 89 files,
  strict mypy over 65 source files, compilation, and source-modularity gates
  also passed.
- the final independent read-only security recheck reported no actionable
  finding and closed the public-reader contamination and advisory-lock ordering
  findings. The reviewer did not execute tests; repeated multi-process load and
  retry fairness remain outside the present evidence.

A final repeated `docker compose build` stalled while resolving external
registry metadata and was stopped after roughly two minutes. This did not
replace or weaken the earlier successful exact-image build evidence: the local
image `sha256:22a63d6a1979ff0144462eb3430bbf413146fc83c99da901a2c2f2a2f9d763e4`
remained available, Compose started it with
`--no-build`, health passed, both migrations were current by exact digest, and
the live database again reported PostgreSQL 18.4 plus pgvector 0.8.2. The
repeated network-dependent rebuild itself is not claimed as a final green gate.

During the final follow-up, an initially created container reported healthy
but its host port mapping accepted and then black-holed PostgreSQL connections.
The diagnosis was a client connection timeout with no server session. Compose
recreated only the local container and network without deleting the named
volume; the expected loopback mapping then appeared, a direct client query
succeeded, and the full PostgreSQL-backed suite passed. The failed
pre-recreation waits are not counted as product test failures.

Subprocess CLI execution is acceptance evidence but is not attributed to the
in-process coverage percentage. Coverage percentage alone is not a persona or
security acceptance criterion.

### Evidence tier

The current product evidence is **mock/support**, **unit**, local PostgreSQL
**integration**, and synthetic **acceptance** only. None of it establishes
real-user judgment fidelity, privacy on a real corpus, or production readiness.

## Private-Root Preflight

Real identity data requires all of the following:

1. a private root outside every Git worktree;
2. a loopback-only PostgreSQL URL;
3. a restricted runtime database role that can append audit receipts but
   cannot update, delete, or truncate them.

Database URLs must state explicit credentials, one database, and a loopback host
directly and may not carry parameters, query options, or fragments.
Connection-shaping libpq environment variables are rejected and psycopg is
given a literal loopback `hostaddr`. This prevents DNS, `host`, `hostaddr`,
`service`, `servicefile`, `dbname`, or passfile-style fallback from overriding
the visible URI authority or loading an undisclosed connection configuration.

Windows Docker uses a named volume because PostgreSQL permission requirements
cannot be satisfied reliably by an ordinary NTFS bind mount. The project makes
no host-storage-product claim. The CLI reports real-data readiness from the
explicit outside-Git, provenance, egress, authority, and runtime-role
boundaries it enforces.

## Model Baselines

`openai/gpt-oss-20b` is the default local reasoner identifier and
`BAAI/bge-m3` is the default embedding identifier. Both adapters accept
loopback endpoints only.
Loopback transport is not proof that the provider is local: private D1-D5
packets remain blocked unless the operator explicitly attests that the
endpoint cannot proxy or forward them elsewhere. CLI receipts report transport
locality separately from provider-local trust. The adapter disables environment
proxies, refuses HTTP redirects, and applies explicit request, evidence, and
response byte limits.
No model weights were downloaded, no live inference endpoint was started, and
neither model's suitability for this user's corpus has been established.

An account-based Codex adapter was deferred. The current Codex CLI does not
provide a verified project-specific isolation boundary that would justify
letting a persona process invoke it against private identity context. The
project does not inspect Codex, ChatGPT, browser, or IDE credential stores.

## Scientific Protocol

The benchmark freezes case hashes before running and groups dependent examples
before a chronological development/holdout split. It compares:

- zero-history;
- declared-profile;
- low-history/recent-context;
- history-rich structured-core;
- simple deterministic baselines.

Predictors now receive a target-free input type that omits hidden decisions and
hidden rationale terms. The support fixtures do not echo each case's target
label into their evidence channels. Current metrics report judgment accuracy,
macro F1, balanced accuracy, coverage, abstention, selective accuracy, paired
decision loss, and fatal-gate counts. Rationale overlap, evidence-demand
fidelity, and meaningful calibration metrics are **not implemented yet**;
non-abstaining synthetic predictions still use a fixed support confidence.
Synthetic fixtures cannot be presented as real-person acceptance evidence.
The initial acceptance state is `not_calibrated` until a real user-audited
holdout and explicit metric contracts establish thresholds.

## Modularity and Quality Gates

The user's no-god-object requirement is enforced as code, not only prose:

- at most 300 physical lines per hand-written Python or SQL file;
- at most 50 source lines per function or method;
- at most 200 source lines per class;
- a written architecture decision is required before any exception;
- Ruff, strict mypy, pytest, branch coverage, Python compilation, Docker
  configuration, and the source-limit checker are handoff gates.
- pytest fails below 70 percent measured branch coverage; that floor is a
  regression guard, not a scientific acceptance threshold.

## What Remains Unverified

- No real export has been supplied, inventoried, approved, or ingested.
- Corpus ownership, third-party exclusions, retention, and deletion policy
  remain user-specific operational decisions.
- No annotation agreement study has been run.
- No declared-only preview has yet been corrected or accepted by the user as a
  scoped representation.
- Real adopted declarations cannot yet be persisted without losing provenance;
  preview is the only enabled real-declaration surface.
- No real temporal holdout or user audit has been run.
- No live gpt-oss-20b or BGE-M3 endpoint has been verified.
- No restricted real-data runtime database role or local-model provider
  attestation has been configured in this implementation task.
- No threshold supports a claim that the system is as close to, or better
  than, the represented user.
- No external sending, tool execution, autonomous promotion, web UI,
  multi-user service, deployment, or release capability exists.

## Next Discriminating Gates

1. Show the declared-only preview to the user and record corrections without
   persistence.
2. Complete and preserve the synthetic unit, integration, and acceptance
   evidence.
3. Ask the user for an outside-Git private root and a local official
   export, then run metadata-only inventory with explicit authorization.
4. Define third-party exclusions and a small branch-aware annotation guide.
5. Implement rationale, evidence-demand, and calibration metric contracts.
6. Audit a small chronological holdout with the real user.
7. Compare structured-core performance with the frozen simple baselines.
8. Only after those results, decide whether model, retrieval, schema, or
   consolidation changes are warranted.

Failure to beat the simple baselines, persistent scope leakage, poor
calibration, or unreliable attribution would falsify the current V1 approach
and require revisiting the representation before adding capability.
