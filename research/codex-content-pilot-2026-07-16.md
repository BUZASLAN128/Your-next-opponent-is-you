# Ephemeral Local Codex Content Parser Checkpoint

## Status

The represented user authorized returning to the private local conversation
corpus. The first content-bearing operation was deliberately limited to a
memory-only parser feasibility check. It was not corpus ingestion, annotation,
persona construction, retrieval, or model inference.

## Governance Boundary

- The input is the explicitly selected canonical local `sessions` and
  `archived_sessions` surface already covered by the metadata checkpoint.
- Ownership is user-reported for the selected local history; structural
  `user` authorship does not prove that every pasted or quoted span belongs to
  the represented user.
- User messages remain `user_turn_unattributed` with an unknown claim holder.
  Assistant messages remain assistant context. System, developer, reasoning,
  tool, attachment, image, and binary content is not normalized as dialogue
  evidence.
- Content exists only in process memory. It is not emitted, persisted, written
  to a private artifact, inserted into a database, or sent to a model.
- The transient derived objects are discarded when the command exits. No
  deletion claim is made for the unchanged source files or for future durable
  artifacts.
- Every event remains interpretation-authority `none`, non-core-eligible, and
  incapable of promotion or action.

These limits close the selected-path, retention, transient-deletion, and
source-attribution questions only for this non-persisting parser check. They do
not settle governance for a durable annotation corpus.

## Implemented Parser Contract

The content pilot is separate from the content-free metadata adapter. It:

- selects at most five canonical regular files across bounded size buckets;
- reads at most 16 MiB total, 4 MiB per file, and 1 MiB per JSONL record;
- caps total records, normalized dialogue events, and per-event text;
- reads through a no-follow stable-file handle and rejects invalid JSONL,
  link swaps, source mutation, or any exceeded limit;
- preserves the source record family, structural speaker, opaque thread and
  turn identities, explicit parent-thread relation when present, content hash,
  source-file hash, sequence position, and repeated-content cluster;
- retains repeated source records rather than silently deduplicating them;
- never fabricates a message-parent edge when the source does not provide one;
- maps untrusted record, payload, and content-part discriminator values to
  fixed public categories before any count reaches the CLI summary;
- returns only a content-free summary from the CLI.

## Public Result

Synthetic unit and CLI tests passed for attribution, exclusion, repeat
clustering, opaque lineage, deterministic selection, malformed and oversized
input rejection, discriminator sanitization, and the no-storage/no-provider
boundary. The discriminator regression was added after an independent privacy
review found that unexpected type strings could otherwise become summary keys.

One bounded real run completed twice. Both runs produced the same content-free
normalized snapshot and the same bounded counts. The private output-root file
count did not change. No raw message, title, working directory, filename,
session identifier, path, hash, date, or corpus count is included in this
repository.

## What This Establishes

The local Codex surface can be parsed deterministically under a small,
fail-closed, memory-only contract while preserving speaker and explicit thread
lineage without laundering a user-role turn into identity truth.

## What This Does Not Establish

This checkpoint does not establish export completeness, durable provenance,
third-party-content classification, annotation agreement, persona fidelity,
safe deletion propagation, model quality, retrieval quality, a learned core,
or readiness to process the full corpus.

## Next Gate

The next experiment is a branch-aware annotation-feasibility pilot, not bulk
ingestion. Its candidate design uses 24 unique evidence windows: 12 sampled
windows and 12 deliberately varied decision/correction windows. Eight windows
are presented a second time without the first label, for 32 total labeling
presentations. Before that experiment writes any private evidence window, the
user must approve its ownership and third-party exclusions, retention period,
deletion lineage, and private artifact contract.
