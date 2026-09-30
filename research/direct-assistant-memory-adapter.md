# Direct Main-Assistant Memory Adapter

**Status: Confirmed scoped architecture direction; partial focused test
evidence and the final synthetic aggregate are reported passing (931 passed,
31 conditional skips, zero failures); real-corpus readiness remains blocked.**
This document records the
approved continuation path for the existing YNOY main assistant. It does not
replace the product constitution or claim that this adapter is a complete
executive agent.

## User-approved scope

The user authorized continuing the existing YNOY application through direct
operations of its main assistant and opening a draft stacked pull request on
the existing work. The memory path uses a local SQLite append store and
deterministic PageIndex prepared-tree navigation. This is a subsystem-scoped
architecture decision. It preserves the existing PostgreSQL V1 core and its
contracts for paths that already depend on them; it does not migrate that core
or revise the immutable product constitution in `AGENTS.md`.

The implementation reuses the existing interaction-review, correction,
replay, and decision-brief contracts. The confirmed store surface is
`DirectMemoryStore`: `record_source_event` captures append-time
`recorded_at`; `record_live_user_input` is a distinct current-user-bound path;
`build_review` calls the native review builder without a provider;
`apply_correction` appends a claim revision with provenance; and `brief`
resolves a project brief with separate `as_of` and `known_at` inputs. The store
also exposes JSONL export and backup operations. The CLI namespace is
`ynoy --private-root ROOT direct-memory [--synthetic]`. Its current command
surface is:

```text
source-event, live-input, tool-result, attribute-authorship, authorize,
review, correct, claim-revision, revision, source, brief, export, backup,
import-document, list-documents, tree, read-nodes, read-pages
```

Every ledger mutation requires `--expected-revision`. Real file inputs must
resolve inside the explicit private root; file outputs use exclusive creation
and must remain outside Git. `StructuralIndex` operations work without
initializing the SQLite ledger.

## Storage and time contract

The local SQLite store is an append-oriented provenance ledger. A source
payload remains unchanged inside an outer storage envelope that binds its
digest and provenance. `record_source_event` records `recorded_at` when the
append occurs; callers cannot supply or backdate it. It is separate from
nullable source `said_at` and event time. Queries separate valid/event-time
`as_of` from `known_at` (when a fact was recorded). Expected revision checks
run under `BEGIN IMMEDIATE`, so concurrent writes against a stale head are
rejected instead of silently rebased.

`known_at` selects the append-time prefix of source events, reviews, correction
wrappers, and claim revisions. `as_of` filters by source event time and native
valid-time scope. Native `correct`, `retract`, and `supersede` operations are
retrospective interpretation revisions over their source evidence. They do
not mean that the world changed at the time the correction was recorded. A
real-world change must be a separate assertion with its own event time and
native validity interval.

The original source payload, digest, and native review `created_at` remain
unchanged. A correction is an appended wrapper event whose `event_time` is the
original source event time (or its source `said_at` when the review has no
event time), preserving source chronology while `known_at` determines when
that interpretation becomes visible. Conflicting
claims remain visible and the decision operation abstains rather than
selecting a truth. These contracts do not establish that an imported claim is
accurate or current.

For a reviewed atom whose prior correction changed effective fields, unsafe
incremental continuation is rejected because it could restore stale fields.
The caller must provide complete typed replacement claims (including a
complete split replacement where a claim is split) or explicitly confirm a
rejected original. This preserves scope and inference semantics.

Each project is partitioned to one live subject. A second live subject is
rejected inside the mutation transaction, and a brief fails closed if legacy
reviews for a project contain mixed subjects.

## Attribution and operation authority

An imported `role=user` label establishes the source role only. It does not
establish that every claim in the content belongs to the current user or the
represented person. A separate `source_authorship` attestation binds the exact
`source_id`, `source_sha256`, and `subject_id`. Imported assistant or third-
party sources cannot be converted into direct-user authorship. Imported user
events cannot carry action intent. The distinct `record_live_user_input`
operation can bind the current user to current input, but ordinary text in that
operation still grants no action authority. A proposal or assistant-authored
statement does not become user evidence through storage, retrieval, correction,
or repetition.

An action declaration requires a separate `AuthorizationIntent` bound to the
exact action, payload digest, subject, and review. `authorize_action` validates
the stored matching intent into a `UserAuthorizationReceipt`; consuming a
write persists the receipt atomically. This defines an auditable authorization
record, not execution of the authorized action.

`tool_verified` requires a dedicated trusted-local-caller import of a tool
receipt. The receipt preserves operation and input/result digests. The claimed
payload must equal the persisted tool result as canonical JSON; a result
explicitly marked `executed: false`, cancelled, or failed cannot support
`tool_verified`. The caller is responsible for capturing the actual tool
result. This receipt has no executor cryptographic attestation, truth oracle,
or execution authority. An arbitrary assistant assertion belongs in
`reported_done` or `uncertain`, not `tool_verified`.

## Prepared-tree navigation

`StructuralIndex` consumes caller-supplied `PreparedDocument` values with a
document name, exact page strings, and a prepared tree. It can import a
document, list documents, read its tree, read nodes, and read pages. Node spans
are bounded, inclusive, one-based page ranges; node IDs are unique within the
document. Stable document identifiers and content hashes support reload and
repeatable navigation.

`NodeRead` separates navigation summary from exact `PageRead` values; page
results include the text, source reference, and hash. Tree summaries may guide
navigation only. Evidence comes from exact supplied page text. This path makes
no OCR claim and does not discover files or scan a corpus on its own. It is
deterministic prepared-tree navigation, not a general semantic search or a
model-generated source interpretation.

Validation bounds a document and JSON input to 64 MiB, JSON nesting to depth
128 and 250,000 items, tree depth to 128, and each tree to 50,000 nodes.
Validated document-scope annotations are removed from the canonical persisted
tree, so equivalent scoped input has the same content identity on an
idempotent retry. Backup publication uses an atomic new-file path and refuses
to overwrite an existing destination.

The index persists a private source bundle containing the exact text, document
name, and navigation summaries. It is a prepared source snapshot, not a
privacy-blind, opaque metadata-only index. The native decision brief remains
unchanged; its integrity digest is carried separately as
`native_brief_hashes`, computed with `canonical_sha256` over the native
payload.

## Privacy and recovery boundary

This authorization covers the source-backed text-snapshot subsystem. It does
not establish readiness for a real conversation corpus or authorize full
pipeline deletion. The current adapter has no canonical external-file binding,
registered erasure/backup producer registry, WAL/SHM cleanup contract, or
interrupted-corpus resume cursor. These are concrete gaps against the
project's [state, privacy, and erasure contract](mathematical-foundation/state-privacy-erasure.md),
which requires a complete, attested producer boundary, erasure parity, backup
scope, future-retry fence, and post-delete independence evidence.

Real-corpus readiness therefore remains blocked until the source binding,
retention and deletion handlers, SQLite sidecar/backup handling, and resumable
import contract are defined and validated, in addition to the existing
represented-user adoption gates. The currently authorized path uses private
artifacts outside Git and makes no model or provider calls, persona adoption,
or executive action.

## Boundaries and evidence still required

This adapter does not require an intermediary model or mandatory embeddings.
It is not evidence of full personality fidelity, executive parity, retrieval
accuracy, or real-corpus performance. It does not make proposals authoritative,
automatically adopt identity claims, or make external actions.

Reported focused evidence includes 49 native-builder/model/hash/correction/
replay regressions, 12 database-focused tests, 21 Windows structural-index
acceptance tests, 33 focused defect cases, 15 frozen external-witness
correctness cases, and six installed-wheel CLI cases. Two witness cases were
deselected because they require a privacy-blind opaque index and external
source mutation, neither of which is in the current API. Full Ruff, mypy over
311 files, source limits, and compileall are reported passing. The installed
`ynoy.exe` exercised SQLite persistence, source review, live-user
authorization, correction/reload, hashes, JSONL, backup, and prepared-index
operations with network, providers, and PostgreSQL blocked.

The initial integrated run reported 900 passed, 31 skipped, and four failed.
The history-test oracle/setup was corrected. Three baseline expiry failures
were verified against the untouched base; a clock-only fixture correction
then passed its three focused tests. The final aggregate run passed 931 tests,
skipped 31, had no failures, reported 197 warnings, and measured 83.54% branch
coverage in 481.88 seconds. The unchanged 70% coverage gate passed. The skips
were database/platform conditional (no `YNOY_TEST_DATABASE_URL`; Windows
symlink/file-identity conditions), so no PostgreSQL-green claim follows.

Additional separate checks passed: 33 focused defect tests; 15 independent
external-witness correctness tests with two deferred-capability cases
deselected; six installed-wheel CLI tests; Ruff; mypy on 311 files; source
limits; compileall; and diff check. The six CLI tests exercised SQLite
persistence, source review, live-user authorization, correction/reload, hashes,
JSONL/backup, and prepared-index operations with network, providers, and
PostgreSQL blocked. The two deselected witness cases require a privacy-blind
opaque index and external source mutation, both outside the current API.

The code-only 53-file review reported no confirmed P0/P1/P2 findings. The final
wheel was rebuilt and installed through the bundled-pip isolated path; the real
`ynoy.exe` ran. The full offline `uv sync` path still encounters Windows
PE-launcher handling; pinned dependencies synced with `--no-install-project`.
The aggregate result establishes synthetic/runtime conformance only. It does
not establish PostgreSQL integration, real-corpus privacy or deletion,
external-source binding, retrieval quality, or persona fidelity. GitHub review
remains pending after the draft pull request.

See [Event 066](conversation-record.md#event-066--scoped-direct-assistant-memory-adapter),
[D-076](decision-log.md#d-076--authorize-a-scoped-direct-assistant-memory-adapter),
[L-051](source-ledger.md#l-051--scoped-direct-assistant-memory-adapter-contract),
the runtime update [L-052](source-ledger.md#l-052--direct-memory-time-authority-and-current-validation),
and [RQ-042](open-questions.md#rq-042--does-the-direct-memory-path-preserve-source-and-decision-boundaries-in-operation).
See [RQ-043](open-questions.md#rq-043--what-privacy-and-recovery-contracts-block-real-corpus-use),
the [erasure contract](mathematical-foundation/state-privacy-erasure.md), and
the [test acceptance boundary](mathematical-foundation/implementation-test-contract.md).
