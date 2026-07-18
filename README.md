# Your Next Opponent Is You.

> **It learns how you judge and communicate—without confusing resemblance
> with authority.**

An open-source, local-first scientific prototype for testing a personal
cognitive core for AI coding agents.

Your conversations with AI contain more than prompts. They contain decisions:
what you accept, reject, correct, defer, and require evidence for. This project
tests whether those decisions can become structured, scoped, versioned memory
that predicts what you would accept in a later coding situation.

AI responses are context. **Your decisions are the signal.**

## Current Status

V1 is an implemented command-line research harness, not a finished virtual
self. It supports synthetic and locally authorized experiments around:

- bounded ChatGPT-export inventory and explicit ingestion approval;
- a bounded, memory-only local Codex content parser that emits no message text,
  artifact, identity claim, database write, or model request;
- a bounded private Codex persona-study preparer with deterministic replay,
  protected temporal holdout, opaque missing-parent lineage anchors, and
  retention-controlled review artifacts;
- speaker, claim-holder, branch, scope, time, and source provenance;
- cold start from no history or explicit user declarations;
- a data-free Manager that starts without PostgreSQL, a private data root, or
  a model provider and generates only non-personal operating memory;
- a non-persisting persona preview from explicitly adopted declarations, with
  empty views and unvalidated confidence exposed rather than inferred away;
- a non-persisting atomic correction lifecycle with hash-linked replay,
  explicit supersession, scope/time filtering, conflict abstention, and
  source/correction identifiers in its decision brief;
- a proposal-only local-model extractor that turns one typed interaction
  receipt into exact-span atomic candidates for explicit user review;
- inspectable, correctable, and deletable derived records;
- Mirror predictions and Advisor proposals with uncertainty;
- frozen temporal benchmark splits and simple baselines;
- local PostgreSQL 18.4 plus pgvector 0.8.2 storage;
- provider-neutral adapters whose transport is restricted to loopback and whose
  private-data access requires a separate local-provider attestation.

The repository has synthetic test evidence plus bounded private correction and
persona-study observations whose content remains outside Git. A pinned
Qwen3-8B Q4_K_M endpoint has been validated locally on loopback and used for
proposal-only private review. A bounded real study package now exists, but its
first model-proposal receipt failed the deterministic review-burden gate and
was retained only as negative evidence. No full conversation corpus has been
ingested into the database, no represented-user annotation has been sealed,
and no result establishes extraction quality, persona fidelity, or real-user
decision prediction.

The correction lifecycle is a private-artifact CLI and Python contract, not a
database schema. The optional model proposes candidates only; correction and
replay remain deterministic, database-free, and unable to promote a persona
candidate into the durable core.

## The V1 Claim

The first falsifiable question is deliberately narrow:

> Does a structured, scoped cognitive core predict a user's later coding
> judgments better than zero-history, declared-profile, recent-context, and
> simple retrieval/rule baselines?

Mirror predicts. Advisor proposes. Neither mode may send, execute, present
output as user-authored, or claim that an external action occurred without
explicit scoped authority. V1 does not automatically promote learned
candidates into the durable core.

Every output carries authoritative `action_status: "not_performed"`,
`authority: "none"`, and a null `action_receipt`. Text returned by a reasoner is
tagged `answer_kind: "untrusted_reasoner_advisory"`; it is never an execution
receipt even if a model's free text falsely says that something was sent or
executed. Cold-start and fixed generic guidance use `system_advisory`.

## Public Code, Private Mind

Git may contain code, schemas, documentation, and explicitly synthetic
fixtures only. The following remain private identity data and must live outside
every Git worktree:

- raw exports and attachments;
- inventory manifests and normalized events;
- user declarations and labels;
- embeddings, derived claims, reports, and model outputs.

Every real-data command fails closed unless its explicit private root is
outside Git. Real review and persona inputs must also resolve inside that same
root. No command discovers a home directory, credential store, or backup tree.
The database is exposed on loopback only. Database URLs require explicit credentials and one database
name; parameters, query options, and fragments are rejected. Connection-
shaping libpq environment variables are also rejected, and the client passes a
literal loopback `hostaddr`, so the visible host cannot be replaced by
`hostaddr`, service files, pass files, DNS, or environment fallback. The
project never reads browser, ChatGPT, Codex, IDE, or provider credential stores.

External adapters receive D0 public/synthetic material only. Private task
content, raw history, derived identity, secrets, and third-party personal data
are blocked before an adapter is invoked. A loopback URL alone is not proof
that its provider is local; D1-D5 use additionally requires
`YNOY_LOCAL_MODEL_ATTESTED=true` after the operator verifies that the endpoint
cannot proxy or forward requests elsewhere.

A ChatGPT `role=user` turn proves the turn author, not the claim holder of every
span. Such turns are therefore imported as unattributed with an unknown claim
holder until a future explicit adoption/attribution step identifies which
claims actually belong to the represented user.

## Architecture

V1 uses ordinary PostgreSQL records and explicit dependency edges. It does not
use a separate graph database, GraphRAG, Graphiti, Mem0, or a hidden framework
that owns identity truth.

```text
read-only export / explicit declaration
                |
       inventory + approval
                |
  source-preserving normalization
                |
 PostgreSQL records + provenance edges
                |
  bounded workspace / Mirror / Advisor
                |
 frozen temporal benchmark + private report
```

The newer review path remains outside that persistence flow:

```text
typed interaction receipt
              |
optional local-model proposal
              |
per-atom user correction receipts
              |
fail-closed deterministic replay
              |
scoped decision brief or abstention
```

Responsibilities are split across small modules for corpus parsing, policy,
typed models, storage repositories, inference, benchmarking, reporting, and
CLI handling. Automated limits reject hand-written Python or SQL files above
300 lines, functions above 50 lines, and classes above 200 lines.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop with Docker Compose for PostgreSQL integration
- an explicitly selected local private root outside Git before any real-data
  review, corpus, database, or durable-persona work
- optional `llama-server` build 9803 for the pinned local extractor experiment

All Python and container dependencies are exact-version pinned. Do not replace
pins with `latest`.

## Setup

```powershell
uv sync --frozen --all-groups
Copy-Item .env.example .env
docker compose up -d --build postgres
uv run ynoy --database-url `
  'postgresql://ynoy:ynoy_local_dev_only@127.0.0.1:55432/ynoy' `
  database migrate
```

The values in `.env.example` are local-development defaults, not shared or
production credentials. The Compose owner account is for migration and
synthetic development only. Real-data commands require a distinct,
non-superuser runtime role that may insert audit receipts but may not update,
delete, or truncate them. After creating that role through your normal local
credential workflow, grant only the repository-defined permissions:

```powershell
psql $env:YNOY_DATABASE_URL `
  -v runtime_role=ynoy_runtime `
  -f scripts/grant-runtime-role.sql
```

Do not put the runtime role's real password in Git or shell history. Point
`YNOY_DATABASE_URL` at that restricted role before any real-data command.

Choose a private root outside the repository:

```powershell
$env:YNOY_PRIVATE_ROOT = 'C:\Users\YOUR_USER\AppData\Local\ynoy-private'
$env:YNOY_DATABASE_URL = `
  'postgresql://ynoy:ynoy_local_dev_only@127.0.0.1:55432/ynoy'
uv run ynoy doctor
```

On Windows, Compose uses a Docker named volume because an ordinary NTFS bind
mount does not reliably satisfy PostgreSQL's Unix permission requirements.
The project enforces an explicit outside-Git root, loopback boundary,
restricted runtime database role, Git exclusion, and no-egress rules. It makes
no host-storage-product claim.

## CLI Workflow

Every successful or policy-denied result is JSON on stdout. Unexpected
diagnostics are redacted and written to stderr.

### 0. Start without history or infrastructure

```powershell
uv run ynoy manager start `
  --task 'How should I review this change?' `
  --project example-repo
```

This path needs no database URL, private data root, conversation export, or
model endpoint. It returns bounded generic guidance and creates an ephemeral
`system_operating_seed`: public system-control rules, zero persona evidence,
an explicitly empty persona memory, and one next learning question. The seed
is not a claim about the user, is not persisted, cannot enter persona
retrieval, and is never promoted into the core. The supplied task remains D1
private task context and is neither stored nor sent by this path. Personal
memory can be added later only through sourced declaration or corpus workflows.

### 0.1 Preview explicit declarations without creating a core

The preview input is structured JSON. Every item must explicitly identify the
user speaker, represented-user claim holder, adoption, source authority,
identity-interpretation plane, and synthetic state:

```json
[
  {
    "speaker": "user",
    "claim_holder": "represented_user",
    "source_authority": "explicit_user_statement",
    "adopted": true,
    "evidence_plane": "identity_interpretation",
    "synthetic": true,
    "kind": "preference",
    "statement": "Prefer small reversible changes.",
    "scope": {"project": "example-repo", "role": "reviewer"}
  }
]
```

```powershell
uv run ynoy persona preview C:\path\to\synthetic-persona.json --synthetic
```

The result is `declared_only` with `low_unvalidated` confidence. It preserves
the statements and receipts, exposes empty behavioral, value,
autobiographical, and personal-metacognitive views, keeps scoped objects
separate, and reports no database, provider, persistence, authority, action,
or automatic core promotion.

For real declarations, set `synthetic` to `false`, omit the CLI flag, and keep
the JSON file inside the explicitly selected local private root outside Git.
Free-form Markdown is intentionally rejected on the real
identity path because it cannot yet carry trustworthy per-item speaker, claim-
holder, adoption, plane, and scope metadata. The preview command does not
write the declarations into the database.

### 0.2 Propose and correct atomic interaction claims

`review propose` accepts one strict `InteractionReceipt` JSON document. The
local model may only propose exact-span interpretations; each candidate stays
`proposed`, `confirmation_required=true`, and `core_eligible=false`:

```powershell
uv run ynoy review propose C:\private\interaction-receipt.json
uv run ynoy review batch C:\private\interaction-review.json --limit 5
```

The batch output supplies each `claim_id` and all eight allowed actions. A
minimal partial correction file is an array of independent atom decisions:

```json
[
  {
    "claim_id": "00000000-0000-0000-0000-000000000000",
    "subject_id": "self",
    "action": "confirm"
  },
  {
    "claim_id": "11111111-1111-1111-1111-111111111111",
    "subject_id": "self",
    "action": "reject",
    "reason": "The proposed interpretation is too broad."
  }
]
```

```powershell
uv run ynoy review apply C:\private\interaction-review.json `
  C:\private\decisions.json
uv run ynoy review replay C:\private\interaction-review.json `
  --receipt C:\private\correction-receipt.json
```

Unanswered atoms remain pending. Later decisions append hash-linked receipts
and supersede history explicitly; they do not rewrite the source. Real inputs
and generated review artifacts must remain inside the private root outside Git.
Add `--synthetic` only for explicitly synthetic fixtures.

### 1. Check readiness

```powershell
uv run ynoy doctor
uv run ynoy database status
```

`doctor` reports `synthetic_ready` until the stricter real-data boundary is
satisfied. Readiness requires an exact name-and-digest match between every
packaged migration and the applied database ledger; missing, modified, or
unexpected migrations block both synthetic operations and real-data use.

### 2. Inventory before ingestion

The first real-data operation is metadata-only inventory. The archive is read
in place and is not extracted or copied into the repository.

```powershell
uv run ynoy corpus inventory C:\private\chatgpt-export.zip
```

The archive reader bounds entry count, item size, total size, and compression
ratio, JSON-item size (16 MiB), JSON nesting (128 levels), conversation nodes
(10,000), branch depth (2,048), and expanded branch-membership work (250,000
pairs), and rejects traversal and link-like entries. Real archives must resolve
outside every Git worktree. Inventory does not grant permission to ingest. Its JSON receipt
includes an `erasure_source_id`; preserve that private identifier to seed a
complete corpus dependency-erasure plan later.

### 2.1 Inventory local Codex metadata without copying conversations

```powershell
uv run ynoy --private-root C:\private\ynoy `
  corpus codex-inventory C:\private\codex-root
```

The Codex adapter inspects only explicitly selected `sessions` and
`archived_sessions` trees, accepts canonical rollout names, reads one bounded
first record per file to validate its type, and never copies titles, working
directories, message text, tool output, filenames, or session identifiers.
Backups, credentials, noncanonical directories, the database, and model
providers remain out of scope. The resulting manifest, counts, dates, opaque
keys, and hashes are private and must stay outside Git.

### 2.2 Run the non-persisting Codex parser pilot

```powershell
uv run ynoy --private-root C:\private\ynoy `
  corpus codex-pilot C:\private\codex-root
```

The pilot deterministically selects no more than five canonical files and
reads at most 16 MiB total, 4 MiB per file, 1 MiB per JSONL record, 20,000
records, and 2,000 dialogue events. It normalizes only structural user and
assistant dialogue in process memory. Raw user turns retain unknown claim
holders and unattributed authority; developer, system, reasoning, tool,
attachment, image, and binary content is excluded from dialogue evidence.

The CLI returns only counts and a private snapshot checksum. It writes no
content artifact, database record, embedding, annotation, claim, or persona
candidate and invokes no model provider. Process exit discards the transient
events. A durable annotation sample requires a separate retention and deletion
decision.

### 2.3 Prepare one bounded private persona study

```powershell
uv run ynoy --private-root C:\private\ynoy `
  study prepare C:\private\codex-root
```

This command does not ingest the complete corpus. It selects exactly 24
canonical files under a 32 MiB annotation-input cap, reserves a distinct
metadata-only temporal holdout, parses no more than 2,000 dialogue events, and
replays the source selection before committing private artifacts. Missing
parent sessions remain opaque lineage anchors; the runtime never opens or
synthesizes absent parent content.

The returned `review_path` and `labels_path` point into the explicit private
root. They contain private identity evidence and must never be copied into Git.
No database or model is used during preparation.

After starting the exact pinned loopback model described below, proposals can
be generated with:

```powershell
uv run ynoy --private-root C:\private\ynoy `
  study propose-labels STUDY_ID
```

The model runs direct and skeptical passes and has no adoption, promotion, or
action authority. If the deterministic review burden exceeds its cap, the
receipt is retained as `unreliable` and no quick-review artifact is offered.
Use `--retry-unreliable` only for the one protocol-permitted linked retry; do
not lower the gate to make a model run pass.

### 3. Approve an exact manifest

```powershell
uv run ynoy corpus approve MANIFEST_ID `
  --operations ingest derive benchmark report `
  --retention-days 30 `
  --third-party-reviewed
```

Approval is tied to the sealed manifest. A changed archive cannot reuse stale
approval.

### 4. Ingest or bootstrap

```powershell
uv run ynoy corpus ingest C:\private\chatgpt-export.zip `
  MANIFEST_ID APPROVAL_ID

uv run ynoy bootstrap import C:\path\to\synthetic-profile.json --synthetic
```

Database-backed bootstrap is currently synthetic-only. The existing table
does not retain speaker, claim-holder, adoption, source-authority, and plane
metadata, so real D3 import and real replacement persistence fail closed with
`real_identity_persistence_unsupported`. Real declarations may be inspected
through the non-persisting persona preview; a schema migration requires a
separate explicit decision. Synthetic import remains bounded to a 16 MiB
source, 10,000 declarations, and 64 KiB per statement and returns an opaque
source record ID for dependency-aware test erasure. Free-form real Markdown is
also rejected until an equivalent provenance-preserving format is defined and
tested.

Synthetic fixtures and private identity records may not share a represented
subject. Inserts and batch ingestion enforce this boundary transactionally;
corrections must remain in the target record's data class. Synthetic and real
inference fail closed on mixed legacy subjects, so a D0 fixture cannot become
real persona evidence or supersede a D3 record.

Library inference must construct `MemoryRepository` with an explicit D0 or D3
plane; there is no unbound default. Each inference read repeats the readiness
check. Plane-filtered inspection uses `MemoryInspectionRepository.inspect_*`,
which deliberately does not implement the inference reader protocol. A busy
subject returns `identity_subject_busy` and rolls back the whole mutation so
the caller can retry; it does not wait in an advisory-lock ordering cycle.

### 5. Ask Mirror or Advisor

```powershell
uv run ynoy mirror predict `
  --task 'Should this patch be accepted?' `
  --project example-repo `
  --role reviewer `
  --risk medium

uv run ynoy advisor suggest `
  --task 'How should I reduce the risk of this migration?'
```

With insufficient personal evidence, Mirror abstains and asks one useful
question. Advisor may offer generic guidance but reports personal fit as
unknown.

### 6. Inspect, correct, and erase

```powershell
uv run ynoy memory inspect
uv run ynoy memory correct RECORD_ID --reason 'scope was too broad'
uv run ynoy erase plan SOURCE_ID
uv run ynoy erase confirm PLAN_ID PLAN_SHA256
```

Erasure is plan-and-confirm, dependency-aware, resumable, and leaves only a
content-free audit tombstone. A bootstrap source ID removes every declaration
derived from that source. Protected mutations and their audit receipt share one
database transaction; the ledger rejects update, delete, and truncate.

### 7. Freeze and run a benchmark

```powershell
uv run ynoy benchmark freeze C:\private\cases.json --name coding-v1
uv run ynoy benchmark run MANIFEST_ID
uv run ynoy benchmark report MANIFEST_ID RUN_ID
```

The benchmark groups dependent examples before chronological splitting and
keeps the holdout hidden from prediction arms. Synthetic results remain
`not_calibrated`; only a real user-audited holdout can define acceptance.

## Local Model Adapters

The first bounded extractor experiment uses official Qwen3-8B Q4_K_M through
`llama-server`. It is a measured experiment, not a permanent product default.
The startup script requires the exact cached artifact, byte count, SHA-256, and
runtime build before it will bind a server to `127.0.0.1`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/start-local-extractor.ps1

$env:YNOY_LOCAL_REASONER_URL = `
  'http://127.0.0.1:18100/v1/chat/completions'
$env:YNOY_LOCAL_REASONER_MODEL = 'ynoy-extractor-qwen3-8b-q4km'
$env:YNOY_LOCAL_REASONER_REVISION = `
  '7c41481f57cb95916b40956ab2f0b139b296d974'
$env:YNOY_LOCAL_REASONER_ARTIFACT_SHA256 = `
  'd98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785'
# Only after verifying the endpoint cannot proxy or forward externally:
$env:YNOY_LOCAL_MODEL_ATTESTED = 'true'
```

`YNOY_LOCAL_MODEL_ATTESTED` is an operator assertion, not an automatic network
proof. Without it, only D0 public/synthetic packets may cross the adapter
boundary even when the URL is loopback. The client disables environment HTTP
proxies, refuses redirects, and bounds reasoner/embedding request and response
sizes. Adapter methods enforce the D0/attested-local data-class gate
themselves; a direct caller cannot bypass it merely by skipping the CLI. A
loopback service cannot redirect the client to another destination. The
startup script does not download weights: it starts only the already cached,
hash-verified artifact and disables server logging and the web UI.

The verified synthetic smoke test produced two source-linked proposals in one
local run. That run establishes local protocol compatibility only—not model quality, persona
fidelity, or a 7B/8B-versus-1–3B benchmark result. Embedding evaluation and an
account-based Codex adapter remain deferred.

## Development Gates

```powershell
uv sync --frozen --all-groups
uv run ruff check .
uv run mypy src
uv run python scripts/check-source-limits.py
uv run python -m compileall -q src tests scripts
uv run pytest
docker compose config --quiet
```

PostgreSQL integration tests use `YNOY_TEST_DATABASE_URL` when it is set. Tests
must use only a disposable local database and must never point at a real
persona store. Pytest enforces a 70 percent branch-coverage floor; this is a
regression gate, not evidence of real-person fidelity or production safety.

## Research Record

The [research hub](research/README.md) preserves the complete decision,
evidence, uncertainty, and falsification trail. The current implementation
checkpoint is documented in the
[V1 implementation record](research/v1-implementation-record-2026-07-15.md),
with security boundaries in the
[V1 threat model](research/v1-threat-model-2026-07-15.md).

Regenerate the local combined research bundle after substantive work:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File scripts/export-all-markdown.ps1
```

The generated bundle is ignored by Git and is not a source of truth.

## License

AGPL-3.0-only. See [LICENSE](LICENSE).
