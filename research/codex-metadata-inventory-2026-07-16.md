# Local Codex Metadata Inventory Checkpoint

## Status

The represented user explicitly authorized a local Codex metadata inventory and
required all personal, machine, session, and internal manifest details to stay
outside the public repository. One real inventory completed under that scope.

## Inspected Surface

The adapter accepts only the explicitly selected canonical `sessions` and
`archived_sessions` trees. Session directories must follow the expected date
layout and files must use canonical rollout names. Backup trees, credential
stores, noncanonical directories, and every other local path remain excluded.

For each accepted file, the adapter records only an opaque source key,
partition, byte size, observed month, and first-record classification. It reads
one bounded first JSON record solely to classify its type; it does not emit the
record, its other fields, any later line, or any conversation content.

## Public Result

- The private manifest was written under an explicit local root outside Git.
- Checksum verification succeeded after the write.
- No title, working directory, message, tool output, filename, raw session
  identifier, or source path was copied into the manifest.
- No identity claim was derived and no database or model provider was called.
- Actual paths, identifiers, dates, sizes, counts, opaque keys, checksums, and
  the manifest itself remain private.

## What This Does Not Establish

This checkpoint is not an official account export, content ingestion, corpus
normalization, annotation study, persona observation, retrieval benchmark,
deletion round-trip, or model comparison. It is a metadata-only map of one
local source surface.

The embedded SHA-256 values are reproducible checksums, not signatures or
authenticity proofs against an editor who can recompute them. The current
single-user threat model also excludes concurrent filesystem replacement by
another process running under the same OS account during a scan or write. A stronger
adversarial boundary would require a quiescent snapshot or platform-specific
handle-based traversal and storage.

Current-tree redaction does not clean older public Git history. Any history
rewrite, force-push, or fresh public-history operation remains a separate
explicit user decision.

## Next Discriminating Step

The later [ephemeral content-parser checkpoint](codex-content-pilot-2026-07-16.md)
completed the next non-persisting format check. The remaining step is to
approve the durable evidence-window governance contract, then run a small,
branch-aware, repeat-labeled, correction-first, proposal-only annotation
pilot.
