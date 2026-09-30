# Direct Main-Assistant Memory Adapter

**Status: Confirmed scoped architecture direction. Historical synthetic
checkpoint `b9f96e3733ae5ddf3f0ccc0b67f956ea6a80af4d` passed 935, skipped 31
conditionally, and had zero failures. That result is not final evidence for
the current P1 remediation. Real-corpus readiness remains blocked.**
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
retrospective interpretation revisions over their source evidence. The
adapter currently supports `correct` and `retract`; it refuses
`operation='supersede'` before consuming authorization because proposals do
not yet carry the canonical active/query-valid same-subject, same-layer,
same-decision-key receipt tuple required by the repository's implementation
contract. The refusal does not implement supersession binding or cycle-safe
supersession. These operations do not mean that the world changed at the time
the correction was recorded. A real-world change must be a separate assertion
with its own event time and native validity interval.

The original source payload, digest, and native review `created_at` remain
unchanged. A correction is an appended wrapper event whose `event_time` is the
original source event time (or its source `said_at` when the review has no
event time), preserving source chronology while `known_at` determines when
that interpretation becomes visible. The adapter's outer,
cross-review `DirectMemoryBrief.unresolved_conflicts` grouping uses subject,
layer, and explicit `fact_key`: independent keys do not create a false
cross-review conflict, while opposite modalities for the same key conflict
even when wording differs. This is an additional adapter-level grouping.
Native per-review `DecisionBrief` conflict detection retains its existing
layer-plus-normalized-prose behavior; native conflict resolution, payloads,
and hashes were not migrated. Outer conflicts remain visible and the adapter
abstains rather than selecting a truth. These contracts do not establish that
an imported claim is accurate or current.

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

The prior integrated checkpoint at `811f6fd` initially reported 900 passed,
31 skipped, and four failed.
The history-test oracle/setup was corrected. Three baseline expiry failures
were verified against the untouched base; a clock-only fixture correction
then passed its three focused tests. The final aggregate at `811f6fd` reported
931 tests passed, 31 skipped, zero failures, 197 warnings, and 83.54% branch
coverage in 481.88 seconds. The unchanged 70% coverage gate passed. The skips
were database/platform conditional (no `YNOY_TEST_DATABASE_URL`; Windows
symlink/file-identity conditions), so no PostgreSQL-green claim follows.

Additional separate checks at that checkpoint included 33 focused defect
tests; 15 independent external-witness correctness tests with two deferred-
capability cases deselected; six installed-wheel CLI tests; Ruff; mypy on 311
files; source limits; compileall; and diff check. The six CLI tests exercised SQLite
persistence, source review, live-user authorization, correction/reload, hashes,
JSONL/backup, and prepared-index operations with network, providers, and
PostgreSQL blocked. The two deselected witness cases require a privacy-blind
opaque index and external source mutation, both outside the current API.

The code-only 53-file review reported no confirmed P0/P1/P2 findings. The
previous wheel was rebuilt and installed through the bundled-pip isolated path;
the real `ynoy.exe` ran. The full offline `uv sync` path still encounters
Windows PE-launcher handling; pinned dependencies synced with
`--no-install-project`. That earlier aggregate establishes synthetic/runtime
conformance only. It does
not establish PostgreSQL integration, real-corpus privacy or deletion,
external-source binding, retrieval quality, or persona fidelity. GitHub review
remains a separate exact-head gate; the earlier checkpoint review does not
cover these changes.

See [Event 066](conversation-record.md#event-066--scoped-direct-assistant-memory-adapter),
[D-076](decision-log.md#d-076--authorize-a-scoped-direct-assistant-memory-adapter),
[L-051](source-ledger.md#l-051--scoped-direct-assistant-memory-adapter-contract),
the runtime update [L-052](source-ledger.md#l-052--direct-memory-time-authority-and-current-validation),
the guard update [L-054](source-ledger.md#l-054--supersession-binding-guard-and-conflict-key-semantics),
and [L-055](source-ledger.md#l-055--supersessionconflict-follow-up-validation),
and [RQ-042](open-questions.md#rq-042--does-the-direct-memory-path-preserve-source-and-decision-boundaries-in-operation).
See [RQ-043](open-questions.md#rq-043--what-privacy-and-recovery-contracts-block-real-corpus-use),
the [erasure contract](mathematical-foundation/state-privacy-erasure.md), and
the [test acceptance boundary](mathematical-foundation/implementation-test-contract.md).

## Historical Follow-Up Validation at Published Head — 2026-09-30

At published head `b9f96e3733ae5ddf3f0ccc0b67f956ea6a80af4d`, the aggregate
passed 935 tests, skipped 31 conditionally, and had zero
failures, with 197 warnings and 83.55% measured branch coverage in 461.27
seconds. This checkpoint is historical, not the final result for the current
P1 remediation. The existing 70% coverage gate passed. Thirty-one focused tests
passed. Six installed-wheel CLI tests passed with model, network, and
PostgreSQL calls blocked; two changed production modules matched the installed
wheel bytes. Ruff, mypy over 311 files, source limits, compileall, and diff
check passed.

The independent witness run passed 14 and explicitly deselected three cases.
Two require deferred corpus APIs. The third expects different explicit fact
keys to conflict based on matching prose, contrary to the formal decision-key
contract. Four tracked tests cover different keys with identical wording,
same-key cases with matching and differing wording, and layer separation. The
independent witness result is not all green. Targeted checks against baseline
`811f6fd` reproduced three failures and two passes; these are historical
baseline results, not current failures.

The new guard refuses supersession before authorization consumption. It does
not implement the binding protocol or cycle-safe supersession. Current test
results establish neither PostgreSQL integration nor real-corpus privacy,
retrieval quality, or persona fidelity. GitHub review remains a separate
exact-head gate; the earlier checkpoint review does not cover these changes.

## P1 Remediation Architecture Update — 2026-09-30

This is a reported implementation contract for the direct-memory remediation
round, sourced to draft stacked PR 2 bot comments and repository paths, with
historical checkpoint `811f6fd`, published head
`b9f96e3733ae5ddf3f0ccc0b67f956ea6a80af4d`, and base `3e545d1`. It records no
new user product decision.

### Payload and data-plane boundary

The immutable strict-JSON payload must be captured before authorization and
verified again when the stored object is reloaded. The private plane is the
default: `DataPlane.PRIVATE`, schema 2, application ID `0x594E4D32`. Synthetic
data requires an explicit `PUBLIC_SYNTHETIC` selection with application ID
`0x594E5332`. The CLI must use separate files, `direct-memory.sqlite3` and
`direct-memory-synthetic.sqlite3`.

Legacy schema v1 and unlabelled index 0.1 are rejected read-only; no automatic
migration is performed. The new index envelope is version 0.2. Its stored
plane is outside content identity, and `structural-index` (private) and
`structural-index-synthetic` (D0) use separate directories. Sources, briefs, and
exports carry the outer plane label; native hashes remain preserved.

### Filesystem creation boundary

New POSIX roots must be owner-only mode 0700 and new files owner-only mode
0600, with owner and link-safety checks. These creation/check rules do not
change existing ACLs or chmod existing paths. Windows ACL behavior is
OS-managed and unverified. POSIX runtime validation is unavailable because
`wsl --list` returned `E_ACCESSDENIED`; this record makes no POSIX-test claim.

### Remediation status and residual findings

At this architecture-only checkpoint, the three P1 items remained
implementation work awaiting gates and review; they were not clean or ready.
The historical 935-pass, 31-skip, 83.55% report
belongs to published head `b9f96e3733ae5ddf3f0ccc0b67f956ea6a80af4d` and is
not the final result for this remediation. Event 068 and L-057 supersede this
interim validation status with the final local candidate results.

Six remote P2 issues remain open, nonblocking, and disclosed: non-monotonic
wall-clock handling at the `known_at` prefix; manual fact-key canonical
guard; index maximum-document admission; tool source-ID whitespace; index
lock initialization race; and partial JSONL publication. Previously fixed
supersession handling remains a safe refusal before authorization when the
canonical binding is missing. The outer brief's subject/layer/fact-key
grouping remains separate from native inner legacy grouping. Deferred
real-archive lifecycle, deletion, and invalidation scope remains unchanged.

## Pre-Fix Local P1 Implementation Checkpoint — 2026-09-30

The frozen-manifest-33 candidate SHA-256
`a3b71e82f04ccad07324db2ac120a6fa147d8bcf38b52910710bb7603189f5c2` passed
the reported local implementation gates. The full aggregate passed 947,
skipped 37, and had zero failures, with 197 warnings and 83.39% measured
branch coverage in 464.19 seconds; the log is
`task/ynoy-remote-p1-aggregate-20260930.txt`. Focused checks passed 73 with six
POSIX skips in 13.93 seconds. The final wheel passed 14 CLI plus plane/index
cases in 3.43 seconds with model, socket, and PostgreSQL calls blocked.
Nineteen changed production sources matched wheel bytes; wheel SHA-256 is
`626267d15aa8bd4653450cdb7ec509578cd5114cbd262a5da389a4bc4df8d2f3`. Ruff,
mypy over 317 files, source limits, compile, and diff checks passed.

The 37 aggregate skips comprise the historical 31 database/platform skips
and six POSIX skips. PostgreSQL and POSIX runtime behavior remain unverified.
Independent Sol/high correctness review remains pending. Security review via
GPT-6.1 Sol/ultra fallback has been dispatched and is running. The primary
Daybreak/high spawn failed with the exact error `Unknown model daybreak`.
Exact-head GitHub review is also pending. The PR remains a
draft and is not production-ready; no clean independent correctness or
security verdict is claimed. The older 935/31/83.55% result remains historical.
Six remote P2 findings remain open and nonblocking, and real-corpus lifecycle,
deletion, and invalidation remain deferred.

## Corrective Review and Post-Fix Status — 2026-09-30

Review of the original manifest-33 candidate found a P1 in ordinary
`correct`: an empty supersessions mapping could be observed while build-clock
state changed after authorization, allowing an inadmissible wrapper to commit
and consume the receipt before reload failed. The source owner reports a fix
that detaches the `MappingProxyType` selection before validation/hash and
moves SQL insert extraction to `correction_records.py`, preserving the native
hash and API.

The manifest-36 candidate SHA-256 is
`9769921c5fb3ef99dc4ead90c0120c3c8883a35bac60049e06b4b83a37e0a1d4`; the
previous manifest-33 hashes are reported unchanged. The focused
correction/auth/history/CLI slice passed 30 in 8.25 seconds. Ruff, mypy over
318 modules, source limits, compile, and diff checks passed. Its full
At that interim report time, the aggregate was still running. L-059 now
records the completed post-fix result. The preceding 947/37/83.39% result is
pre-fix and not final post-fix evidence.

The independent reviews also deduplicated one additional open P2 at
`payload_snapshot.py:205`, concerning partial binding of correction-derived
state/kind/time/revision. A helper/memory probe accepted wrong state if the
row-unkeyed digest was recomputed, but there is no end-to-end corrupted-file
proof and native brief replay still receives the correct receipt. It remains
unfixed. Seven P2 findings are now open: six remote and one local. The
source/transcript review reported no P0. At that report time, the P1 fix
awaited final delta-security review; L-060 now records the completed review
and closure. Exact-head GitHub review remains pending. The PR is still draft
and not production-ready.

## Final Post-Fix Local Validation — 2026-09-30

The manifest-36 candidate SHA-256
`9769921c5fb3ef99dc4ead90c0120c3c8883a35bac60049e06b4b83a37e0a1d4` passed
the full aggregate: 949 passed, 37 skipped, zero failed, 197 warnings, and
83.39% measured branch coverage in 472.95 seconds. The log is
`task/ynoy-correction-final-aggregate-20260930.txt`. The final wheel passed 16
cases in 4.45 seconds; 21 production sources matched its bytes. Wheel SHA-256
is `0234181432d824ac04e8a19a34377ae0470035b2a1fe4a58eceec39c7187d28d`.
Ruff, mypy over 318 modules, source limits, compile, and diff passed.
L-059 also retains the valid 30-test focused correction slice and the
file-backed baseline comparison (one failure, one pass).

The 947/37/83.39% manifest-33 aggregate is pre-fix; the earlier 935/31/83.55%
result is older history. Original-candidate general correctness review
concluded with no remaining P0/P1 and one P2; seven P2 findings remain open.
At this interim status checkpoint, GPT-6.1 Sol/ultra was actively reviewing
only the three-file P1 delta, with verdict pending. L-060 records its completed
review and P1 closure. Exact-head GitHub review remains pending and the PR
remains draft. CI, POSIX runtime, PostgreSQL, and real-corpus
lifecycle/deletion gaps remain.

**Delta-security closure update:** GPT-6.1 Sol/ultra completed the bounded
review of the three-file P1 fix and closed the P1 with no residual P0/P1 in
that fix. Independent probes exercised the real native schema-2 in-memory
SQLite path at both clock callbacks: returned and persisted supersessions
remained empty, correction and claim reloads succeeded, and authorization
reuse was rejected. All 36 manifest hashes matched before and after; manifest
33 remained unchanged. Seven P2 findings remain open, exact-head GitHub review
is pending, and the PR remains draft. See L-060.
