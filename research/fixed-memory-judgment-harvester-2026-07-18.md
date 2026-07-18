# Fixed-Memory Judgment Harvester Checkpoint

> Date: 2026-07-18
> Status: private represented-user audit package ready
> Scientific status: selection apparatus proven; persona quality not evaluated

## User Direction

The user asked the project to continue processing the large private history,
produce a tangible result, and keep the remotely operated machine responsive.
This authorized bounded local corpus processing and testing. It did not
authorize a model run, database migration, automatic adoption, corpus upload,
or publication of private source or derived identity data.

## Implemented Contract

The new harvester reads canonical Codex JSONL records as a stream. One
checkpoint retains only a fixed candidate reservoir and a short bounded context
window. Public hard limits cover files, total input bytes, file bytes, line
bytes, records, normalized events, wall time, retained candidates, context,
artifact output, metadata entries, and checkpoint revisions.

Selection uses a versioned deterministic vocabulary for decisions,
corrections, evidence demands, scope changes, abstention, and outcome feedback.
A label-blind SHA-256 order spreads inspection across the eligible source
universe instead of concentrating every early checkpoint in one chronological
region. Candidate ranking and diversity ties use deterministic hashes rather
than process randomness or model confidence.

Every retained focus remains `claim_holder=unknown`,
`user_turn_unattributed`, ineligible for a benchmark, and ineligible for the
core. Assistant, developer, system, tool, subagent, duplicate, quoted, pasted,
imported, oversized, empty, and structurally uncertain material is excluded or
quarantined. Corpus text is treated as inert evidence, never as an instruction.

## Replay and Private Artifacts

The cursor binds the source study, protected-holdout freeze, stable-time
boundary, selector configuration, exact source receipt, file digest, metadata,
record boundary, and revision. A changed source, missing checkpoint, stale
binding, invalid offset, or reordered chain fails closed. The active resume
anchor is rehashed; earlier completed files are not all rehashed on every
checkpoint because this is explicitly a progressive source, not a frozen
snapshot. Candidate identity is derived from the stable source-study binding
rather than a transient run ID, so unchanged-source regeneration is
reproducible.

Each revision writes an indexed checkpoint, represented-user review Markdown,
and structured label template through the existing private persona-study
artifact producer. These artifacts inherit retention, dependency tracking,
tamper detection, and deletion behavior. No corpus-derived content or runtime
identifier is written to Git.

## Runtime Evidence

The first real attempt exposed a Windows metadata-identity mismatch:
`DirEntry.stat()` reported an unusable identity while the opened descriptor and
path reported the stable identity. The implementation now uses `os.stat()` for
discovery, preserving the existing descriptor/path equality check rather than
weakening the link-swap guard.

The corrected real run reached the configured `audit_ready` state under the
fixed checkpoint limits. Repeated private operator review then exposed more
apparatus defects: delegated provenance could be cleared by later session
metadata, identical focuses could survive through different source records,
runtime and editor wrappers could enter context, a filename could trigger the
word `test`, a short operational fragment could pass an evidence-only rule,
and an imported review block could look like a user judgment. Each defect was
converted into a deterministic exclusion or regression test before another
private package was produced.

The latest bounded package did not reproduce those known focus-contamination
classes under operator and independent inspection. Ordinary dialogue about an
external reference or tool can still appear in the explicitly labeled context;
context is never attributed or admitted as persona truth. This is qualitative
selector-debugging evidence, not represented-user ground truth or a precision
estimate. No model, provider, database, embedding, migration, or automatic
promotion was used. Earlier
development evidence also showed that purely chronological traversal could
over-concentrate a small reservoir; label-blind deterministic source order
corrected that apparatus defect.

Exact paths, IDs, hashes, source dates, corpus counts, candidate text, signal
aggregates, and machine measurements remain private.

## Synthetic Evidence

Focused synthetic tests additionally cover:

- all six signal classes and the no-signal path;
- speaker, authority, subagent, quoted, pasted, and duplicate exclusions;
- fixed context, reservoir, discovery, byte, record, event, and time limits;
- deterministic order and unchanged-source regeneration;
- partial-file resume, record-boundary replay, idempotency, and source mutation;
- private artifact integrity, retention-aware deletion, and regeneration;
- sticky delegated provenance, cross-source focus deduplication, inert context
  filtering, imported review rejection, filename false positives, and short
  low-signal evidence requests;
- CLI denial of database, model, and provider use.

The expanded focused contract suite passed 62 tests. Final validation against
the disposable loopback `ynoy_test` database passed 561 tests with one
qualified platform skip and 85.54 percent branch coverage. Lint, formatting,
strict typing, compilation, source limits, and whitespace checks also passed.

## What This Proves

The project can now locate a small, diverse, high-signal review set from a much
larger local history without loading that history into memory. The output is
replayable, source-bound, private, deletable through the existing producer, and
explicitly unable to become persona truth by itself.

## What This Does Not Prove

This checkpoint does not establish represented-user precision, persona
similarity, decision prediction, calibration, holdout performance, branch-
complete lineage, immutable full-source snapshot, full-corpus completion, model
quality, or safe promotion. The `audit_ready` label means only that the
configured human-review package is structurally ready.

## Next Discriminating Check

The represented user should confirm or correct the private review labels. The
operator audit is sufficient to debug known contamination classes but cannot
substitute for authorship ground truth. After the labeling rule and acceptance
threshold are frozen, measure selector precision and false attribution. Only
that result may justify opening a separately frozen extractor comparison; the
8B model remains disabled for this checkpoint.
