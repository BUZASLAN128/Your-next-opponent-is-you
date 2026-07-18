# Bounded Private Persona Pilot

> Date: 2026-07-18
> Status: private pilot artifacts produced; model proposal gate remained unreliable
> Scientific status: no persona-quality or calibration claim

## User Direction

The user explicitly authorized resuming real local corpus processing and asked
the system to begin producing tangible persona material. The user also required
that the approximately large local history be processed by bounded software
rather than loaded into memory, because the machine was being operated
remotely and other applications had to remain responsive.

This direction authorizes a bounded private pilot. It does not authorize
committing corpus-derived data, uploading it, migrating the personal database,
downloading a model, accepting unreliable output, or ingesting the entire
history in one operation.

## Public and Private Boundary

The selected Codex source and every generated artifact remained under explicit
local paths outside every Git worktree. This public record intentionally omits:

- source and artifact paths;
- session, study, manifest, proposal, and receipt identifiers;
- corpus sizes, dates, counts, hashes, or content;
- generated labels, model text, inferred traits, and behavioral aggregates.

Only implementation behavior, evidence class, failure class, and unresolved
scientific consequences are recorded here.

## Bounded Execution Sequence

### Ephemeral parser

The existing content pilot processed a deterministic bounded sample with its
public caps: no more than five canonical files, 16 MiB total input, 4 MiB per
file, 20,000 records, and 2,000 normalized dialogue events. It used neither a
database nor a model and discarded transient content at process exit.

### Private persona study preparation

The study preparation path selected no more than 24 canonical files and 32 MiB
of annotation input, reserved a distinct metadata-only temporal holdout, and
performed an independent deterministic source replay. It wrote a private
review package, label template, blinded presentation set, evaluator manifest,
holdout freeze, and deletion canary proof under retention-controlled private
storage.

No source file was modified. No database, embedding provider, external model,
persona promotion, or action path was used.

### Local proposal run

The already cached, pinned Qwen3-8B Q4_K_M artifact was started through the
hash-verified loopback runner with a reduced 2,048-token context, one parallel
slot, disabled reasoning mode, disabled server logging, and no web UI. The
model processed blinded cards sequentially through direct and skeptical
passes. The model process was stopped after the bounded run.

The primary proposal receipt exceeded the deterministic review-burden gate and
was classified `unreliable`. The system persisted that failed attempt as
private negative evidence, produced no quick-review artifact, claimed no
persona quality, and promoted nothing.

One protocol-permitted retry was attempted with the same bounded runner. The
retry stopped after abnormal duration and idle inference evidence rather than
keeping the remote machine occupied. No retry receipt or partial promoted
artifact was created, and the model process was stopped. The original failed
receipt remains the only immutable proposal result from this pilot.

## Real-Corpus Defect Found

The first study-preparation attempt failed closed because a canonical session
referenced a parent thread absent from the selected source universe. Treating
that case as no lineage would allow related children to cross annotation and
holdout. Rejecting every missing parent, however, makes ordinary partial local
history unusable.

The runtime now represents an unresolved parent as a deterministic,
domain-separated opaque anchor. It never opens or synthesizes missing parent
content. Children sharing one missing parent remain in one lineage component;
different missing parents remain separate. Explicit cycles, conflicting
parents, blank or wrong-type parent metadata, stale plan bindings, and combined
annotation/holdout closure overlap fail closed. Explicit null remains a valid
root representation.

The lineage graph was moved into a separate responsibility module so the
holdout planner remains below the repository modularity limits.

## Evidence

### Unit and integration-support evidence

Synthetic tests cover:

- shared and distinct missing-parent anchors;
- cycle rejection;
- invalid and explicit-null parent metadata;
- raw-ID non-disclosure in lineage receipts;
- combined annotation/holdout anchor overlap;
- stale component binding rejection;
- deterministic study preparation and existing source-security behavior.

The bounded real run establishes live local parser, study-preparation, private
artifact, loopback model, rejection-gate, cleanup, and resource-feasibility
evidence for this machine. It does not establish general product acceptance.

### Resource evidence

The corpus stages remained at their configured byte, file, record, and event
caps. The 8B model was the dominant memory consumer, ran as one process, and
was removed after use. The pilot produced no out-of-memory error and left no
model listener running.

Exact machine capacity and runtime measurements remain private operational
metadata and are not part of the public repository.

## What Was Produced

The private root now contains:

- a represented-user review Markdown file;
- a structured labels template;
- blinded annotation presentations and evaluator windows;
- an immutable study and protected-holdout manifest;
- an immutable primary model-proposal receipt classified unreliable.

These are inspectable pilot artifacts, not an active cognitive core. The model
receipt may be studied as negative evidence but must not seed a persona,
calibration mapping, policy, authorization tuple, or benchmark target.

## What This Proves

The checkpoint proves that the current software can read a small real slice
without loading the whole corpus, preserve speaker and source lineage, produce
private review artifacts, call one pinned local model through bounded loopback,
reject an unreliable proposal run, and clean up its model process.

It also proves that missing local parent sessions can be represented
conservatively without erasing the dependency edge or reading absent content.

## What This Does Not Prove

The checkpoint does not prove:

- that the generated sample contains enough judgment-bearing user evidence;
- that the model resembles the user or predicts a later decision;
- that stable model outputs are correct or user-authored;
- that the current random/bucketed file selection finds high-signal decisions;
- that the local model retry behavior is operationally adequate;
- that the protected holdout has labels or may be opened;
- that any calibrated probability, baseline winner, or threshold exists;
- that the entire corpus can be persisted, searched, erased, or regenerated;
- that a real authenticator or automatic promotion path exists.

Persona quality therefore remains `not_calibrated/inconclusive`.

## Next Discriminating Step

The next implementation candidate is a resumable, streaming high-signal
harvester. It should inspect canonical files sequentially under a private
cursor, keep a small fixed-size candidate reservoir, and prefer structural
user turns containing decisions, corrections, evidence demands, scope changes,
and outcome feedback. It must preserve provenance and unknown attribution,
never execute corpus instructions, and never load the corpus or candidate set
without a fixed cap.

Before implementation, the selector contract must freeze:

1. maximum bytes, files, records, events, wall time, and private output size per
   checkpoint;
2. deterministic signal features and tie order that do not use holdout labels;
3. restart-safe cursor and exact-source binding;
4. duplicate, branch, quoted-text, assistant-text, and third-party exclusion;
5. private deletion and regeneration behavior;
6. a small represented-user audit that measures precision before expansion.

The current unreliable proposal receipt should be used to improve selection
and protocol design, not to lower the safety gate.
