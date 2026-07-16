# V1 Private-Persona Threat Model

> Date: 2026-07-15
> Status: implemented minimum contract; synthetic and local integration
> evidence only
> Scope: single-user local scientific CLI and its private data lifecycle

## Security Objective

Prevent a personal research corpus, derived identity, credentials, and action
authority from crossing an unapproved boundary or acquiring false provenance.
The safest V1 default is fully local identity processing with external
reasoning disabled for anything except D0 public or explicitly synthetic data.

Security controls protect confidentiality, attribution, reversibility, and
authority. They do not prove that a derived persona is semantically correct.

## In Scope

- user-selected ChatGPT-style ZIP input and canonical local Codex metadata;
- private root and local PostgreSQL storage;
- inventory, approval, ingestion, derivation, benchmark, report, correction,
  and erasure flows;
- loopback reasoner and embedding adapters;
- potential external provider boundary, which is deny-by-default;
- public Git repository and generated local artifacts.

## Explicitly Out of Scope for V1 Claims

- a compromised kernel, OS administrator, hypervisor, or physical-memory
  examiner;
- compromise of a model provider's own infrastructure;
- multi-user or network service isolation;
- production backup, disaster recovery, or remote deployment;
- concurrent filesystem replacement by another process running under the same
  OS account while an inventory or artifact write is in progress;
- autonomous external actions or communication, which are not implemented.

## Protected Assets

| Asset | Classification | Main failure |
| --- | --- | --- |
| Raw export and attachments | D2/D5 | Git, provider, log, or cross-user disclosure |
| Normalized events and declarations | D2/D3/D5 | Speaker laundering or unauthorized reuse |
| Derived claims, embeddings, reports | D3 | Identity reconstruction, drift, or undeletable residue |
| Credentials and sessions | D4 | Cache scraping, logging, argument or crash disclosure |
| Provenance and dependency graph | D3 metadata | False authority or broken deletion cascade |
| Audit receipts | Sensitive metadata | Becoming an immutable second corpus |
| Action authority | Protected control plane | Prediction silently becoming execution |

## Trust Boundaries

1. **Public Git boundary:** code, schemas, docs, and synthetic fixtures may
   cross; real raw or derived identity may not.
2. **Private filesystem boundary:** real artifacts always require an explicit
   outside-Git root. Review and persona inputs must also resolve inside that
   root; no home, backup, or credential-store discovery is permitted.
3. **Database boundary:** PostgreSQL must use loopback;
   the URI requires explicit credentials/database and forbids connection
   options, connection-shaping libpq environment variables are rejected, and
   the client forces a literal loopback `hostaddr` so the visible host cannot
   be replaced by DNS, environment, service, or passfile settings.
   Real data additionally requires a non-superuser runtime role that can append
   but cannot update, delete, or truncate audit receipts.
4. **Adapter boundary:** transport loopback and provider locality are separate.
   A loopback endpoint is trusted for D1-D5 only after explicit local-provider
   attestation; otherwise it is treated like an external adapter and receives
   D0 only.
5. **Authority boundary:** model output is a hypothesis or proposal, never
   evidence, user speech, permission, or proof of action.
6. **Credential boundary:** provider-owned clients own credentials; YNOY does
   not inspect their stores.

## Threats and V1 Controls

| Threat | Control | Remaining uncertainty |
| --- | --- | --- |
| Real identity committed to Git | Commands reject private roots inside any Git ancestor; fixtures require an explicit synthetic marker | A user can still manually copy private files outside the CLI |
| Local Codex content or credentials enter an inventory | Only canonical session trees are traversed; backup and credential paths are excluded; traversal and the single first-record read are bounded; manifest fields cannot contain raw locators or conversation fields | The result is a live local snapshot, not proof of account-export completeness |
| Codex manifest modification is mistaken for authenticity | Strict model validation and reproducible SHA-256 checks reject accidental or naïve changes before storage | A writer who can change the manifest and recompute checksums is not detected; the checksums are not signatures |
| Concurrent path replacement redirects a scan or write | Link, junction, inode, size, time, second-discovery, and output-containment checks fail closed in tested races | Full same-user adversarial TOCTOU resistance requires quiescent snapshots or platform-specific handle-based traversal and storage |
| Private artifacts disclosed by local filesystem access | Commands keep artifacts under one explicit outside-Git root and never treat storage state as identity, authority, or capability proof | Host storage-product verification and multi-process account isolation are outside the current project boundary |
| Archive traversal or link escape | Real archives must also be outside Git; no extraction occurs; absolute, parent, backslash, drive, NUL, and symlink members are rejected | Novel ZIP parser bugs remain possible |
| Decompression or resource bomb | Source bytes, entries, member bytes, total expansion, 16 MiB per JSON item, 128 structural levels, 10,000 conversation nodes, 2,048 branch depth, 250,000 branch-membership pairs, bootstrap bytes/statements/count, and compression ratio are bounded; JSON uses a contiguous streaming buffer | Default bounds need real-export measurement |
| Source changes after approval | Manifest seals source digest and shape; ingestion rehashes and rejects mismatch | Filesystem/hardware compromise is out of scope |
| Assistant or pasted text becomes user truth | Assistant turns retain assistant authority; a user-role turn is stored as `user_turn_unattributed` with unknown claim holder until span-level adoption is reviewed | Real export variants and a human attribution workflow still need audit |
| Repetition becomes independent evidence | Origin clusters and derivation edges preserve dependence | Consolidation policy is not yet scientifically validated |
| Imported prompt executes instructions | Corpus content is inert and the parser has no tool/network behavior | A later model adapter still needs prompt-injection evaluation |
| Private identity reaches a provider | Reasoner and embedding methods themselves block D1-D5 before an unattested adapter invocation; loopback alone is not trust; environment proxies are disabled; redirects are refused; requests and responses are bounded; no silent fallback | Provider locality is not independently verified by the project, and covert D0 leakage must be tested |
| Credential or account confusion | No credential-store reads; no account-based adapter; loopback-only local endpoints; DB URI query/fragment options that could load service or pass files are rejected | Future official integrations need account/workspace binding tests |
| Provider response gains authority | Response authority is none and no core-promotion path is implemented | Future consolidation code could regress this boundary |
| Synthetic fixture contaminates private identity | Subject-scoped transaction locks reject D0/private coexistence, mixed ingestion batches, cross-class replacements, and subject/scope mismatch; public inference requires one explicit plane and rechecks mixed legacy subjects; inspection has a non-inference interface | A future namespace or schema change must preserve the same fail-closed invariant |
| Identity-plane lock ordering deadlocks | Subject locks use non-blocking transaction-scoped acquisition; contention returns retryable `identity_subject_busy` and rolls back the complete operation instead of entering an advisory-lock wait cycle | Higher-level bounded retry policy remains unimplemented |
| Correction leaves stale belief | Revision and supersession lineage retains the correction; mutation and receipt share one transaction | Real report regeneration behavior needs acceptance evidence |
| Bootstrap source cannot be purged | Every imported bootstrap file gets one opaque source record; all declarations expose that source ID and source-level erasure traverses them | Existing pre-migration rows retain only record-level fallback identity |
| Deletion leaves derived identity | Plan-and-confirm erasure traverses corpus, bootstrap-source, direct derived-record, and artifact dependencies and records a content-free tombstone | Backups/provider residuals are not implemented or claimed |
| Audit log mutates or leaks content | Packaged/applied migration names and digests must match exactly; protected DB mutation and receipt commit atomically; UPDATE, DELETE, and TRUNCATE are blocked; real data rejects superuser/audit-mutation roles; receipts contain no raw text/model output | A database owner or OS administrator remains outside the claimed boundary |
| Mirror silently acts as user | Output authority is none; canonical action status is always `not_performed`; reasoner text is tagged untrusted advisory; action receipt is null; send/execute/delegate surfaces do not exist | Future agent integration remains a separate decision gate |

## Minimum Acceptance Scenarios

The V1 suite must cover:

- real-artifact paths inside Git are rejected without changing Git status;
- every real artifact root stays outside Git and real review/persona inputs
  remain inside that explicit root;
- database URI target/config overrides are rejected before any connection;
- libpq environment target/config overrides are rejected and the client forces
  a literal loopback host address;
- synthetic cold start works without a real-data root;
- D0 and private identity cannot enter one subject, including in one ingestion
  batch or through correction, and rejection leaves data and audit unchanged;
- synthetic and real inference reject a mixed legacy subject before retrieval;
- public library inference cannot be created without a D0/D3 plane, inspection
  cannot satisfy the inference reader protocol, and lock contention fails
  promptly without partial writes;
- D1-D5 egress is denied before adapter execution;
- assistant-authored identity claims retain assistant authority;
- unreviewed user-role spans remain unknown claim holders until adoption is
  explicitly attributed;
- repeated source material retains one origin cluster;
- traversal, symlink, oversized source, expansion, compression, deep nesting,
  oversized branch graph/work, oversized bootstrap, and malformed JSON inputs
  fail with stable policy codes;
- local Codex inventory rejects noncanonical directories, links, source
  mutation, inode swaps, and resource-limit overflow while copying no raw
  locator or conversation field;
- stale manifest approval cannot ingest a changed archive;
- append-only audit records reject update, delete, and truncate, and an audit
  failure rolls back the protected mutation;
- missing, modified, or unexpected migrations block doctor readiness and data
  operations;
- correction preserves revision lineage;
- corpus, bootstrap-source, and direct derived-record erasure removes every
  dependent private record and can resume safely;
- audit tombstones contain no deleted content;
- Mirror and Advisor never fabricate evidence or action receipts;
- adversarial reasoner text cannot change canonical no-action status or become
  an action receipt;
- an unattested loopback proxy cannot receive D1-D5 task or evidence;
- a loopback adapter cannot follow an external redirect or accept unbounded
  input/output;
- an end-to-end synthetic CLI run produces only private local artifacts.

Unit evidence may close pure classifiers and typed contracts. PostgreSQL
integration evidence is required for append-only audit, idempotency, correction,
and deletion lineage. Synthetic acceptance is required for the CLI boundary.
None of those tiers closes real-person privacy or persona fidelity.

## Evidence Basis

- [W3C PROV-DM](source-ledger.md#s-052--w3c-prov-dm) motivates explicit
  attribution, derivation, quotation, revision, and invalidation, but not
  semantic truth.
- [MINJA](source-ledger.md#s-028--minja),
  [Hidden in Memory](source-ledger.md#s-062--hidden-in-memory), and
  [MemGhost](source-ledger.md#s-063--memghost-and-whisperbench) motivate
  delayed persistent-memory poisoning tests.
- [Codex authentication](source-ledger.md#s-069--codex-authentication) does not
  grant this project permission to inspect or reuse Codex credentials.
- [OpenAI data controls](source-ledger.md#s-070--openai-api-data-controls) show
  why provider/API use is not equivalent to local-only or universal
  zero-retention behavior.

## Residual Risk and Stop Conditions

Real corpus, database, and durable-persona work must stop if the selected path,
ownership, third-party exclusions, retention, deletion, or source attribution
is unclear. The project makes no host-storage-product claim; provenance,
correction, egress, and authority controls remain independent. External
reasoning must stop if destination, account, retention, data class, or approval
is unknown. Any evidence of speaker laundering, scope leakage, undeletable
derived identity, fabricated receipts, or silent authority expansion blocks
promotion to a broader pilot.

D-046 permits one narrower diagnostic without relaxing this stop condition.
Its selected path is explicit, possible third-party or quoted spans remain
unattributed D2 source content, no semantic interpretation occurs, and no
content or derived event survives process exit. Any retained evidence window,
annotation set, database record, report, model input, or persona candidate
still requires the unresolved ownership, exclusion, retention, and deletion-
lineage contract.

The threat model must be revised before adding network service exposure,
multi-user access, provider egress beyond D0, automatic promotion, external
communication, tool execution, backup, or deployment.
