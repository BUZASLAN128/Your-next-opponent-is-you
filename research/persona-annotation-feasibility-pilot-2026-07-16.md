# Persona Annotation and Protected-Holdout Pilot — 2026-07-16

## Current Result

The bounded real-corpus annotation pack is reproducible and private. Its
replacement evaluator freeze now uses canonical rollout-filename session-start
order at metadata level. This is still not persona-quality evidence. Event-time
order remains unverified because no holdout dialogue has been opened; no target
label, predictor, or model has been opened or run on the real holdout.

The active private pack has the fixed 24+8 annotation shape and the fixed
metadata-only protected-holdout shape.
Its represented-user label draft remains empty. The superseded empty pack and
the verified staging replacement were deleted after the current pack succeeded,
leaving only the promoted private run.

## Safety and Scientific Contract

- The real source remains unchanged and outside Git.
- Annotation selection is limited to 24 stable source files, 32 MiB total
  input, and fixed record and event budgets. Files changed in the prior five
  minutes are excluded.
- Eight to twelve later canonical rollout sessions are reserved before
  annotation selection. Only their bounded first `session_meta` record is read.
  Their dialogue content is not passed to the parser or predictor.
- Annotation files strictly precede the protected holdout boundary by the
  canonical rollout filename's session-start timestamp. Explicit thread-parent
  lineage components cannot cross the boundary. This does not prove event-time
  ordering inside the sealed files.
- Exact content duplication remains explicitly unchecked until the holdout is
  opened after annotation sealing. Scoring must fail closed if an annotation
  duplicate is found then.
- Annotation source parsing occurs sequentially. The source is released and
  independently reloaded from disk before source, selection, holdout, window,
  and blind-map receipts are compared.
- Structural `user` role remains `USER_TURN_UNATTRIBUTED` with unknown claim
  holder until the represented user labels it.
- Completed labels require a local `completed_by=represented_user` operator
  attestation, exact focus spans, the fixed vocabulary, and all 32 presentation
  IDs in immutable order. It is not cryptographic identity authentication.
- Unknown, quoted, pasted, mixed, third-party, non-endorsed, or hypothetical
  material cannot enter persona. Unknown identity or decision fields require
  abstention.
- The first completed 32-label submission and its raw blind-repeat agreement
  receipt become immutable even when a pair disagrees. Any mismatch creates a
  separate represented-user adjudication draft; it never rewrites the initial
  judgments.
- The annotator pack and evaluator map use separate private storage roots.
  This is operational separation, not cryptographic blinding or access control.
- Only the current represented-user label or adjudication draft is mutable.
  Initial submissions, evaluator records, and every other artifact are
  hash-checked and fail closed on tampering.
- Derived artifacts and deletion tombstones expire after seven days. Expiry is
  enforced on each store-backed study access; no background deletion guarantee
  is claimed.
- The deletion check is a disposable canary round-trip. It does not prove
  source deletion or whole-corpus erasure.
- Junctions, symbolic links, traversal, corrupt indexes, incomplete expiry
  purges, source overlap, lineage overlap, exact training overlap, duplicate
  holdout cases, future evidence, and wrong-scope evidence fail closed.

## Content-Free Real Runtime Evidence

The corrected replacement run produced:

- 24 unique annotation windows and 32 presentations;
- eight blind repeat presentations;
- both annotation partitions satisfied their configured bounds;
- the configured minimum protected-holdout shape passed;
- the bounded annotation event budget passed without publishing a
  corpus-dependent count;
- strict canonical filename session-start ordering and no explicit lineage
  overlap; event-time ordering remains unverified;
- matching independent source and holdout replay receipts;
- one mutable empty 32-label draft and no completed label;
- no holdout dialogue access, targets, predictors, database, model provider,
  external upload, or automatic core promotion.

The source corpus was not modified or deleted. The superseded pack was removed
only after its 32 labels were verified empty and the staging replacement had
passed the full artifact contract. The staging copy was removed only after the
same selection and freeze sources were reproduced in the original private root.

## Synthetic Baseline Evidence

A separate D0 synthetic fixture now exercises six target-isolated baselines:

| Baseline | Coverage | Abstention | Selective accuracy |
|---|---:|---:|---:|
| Zero abstain | 0.00 | 1.00 | 0.00 |
| Low recent-three | 1.00 | 0.00 | 0.33 |
| History frequency | 1.00 | 0.00 | 0.33 |
| History lexical | 1.00 | 0.00 | 1.00 |
| History declared | 1.00 | 0.00 | 0.33 |
| History structured | 1.00 | 0.00 | 0.33 |

All synthetic predictions report complete provenance. Changing every hidden
target leaves predictor outputs identical and changes only scoring, which is a
direct target-leakage check. These three synthetic cases are mock/support
evidence only; their numbers are not acceptance thresholds or evidence that
lexical retrieval will work on the represented user.

## Reviewer Findings and Disposition

| Finding | Disposition |
|---|---|
| The original two-way annotation partition was not a protected holdout | Kept as annotation-only and added a distinct later-by-session-start metadata-only holdout freeze before annotation parsing |
| Expiry depended on access and could stop at a scan cap or corrupt run | Removed the cap, continued across invalid runs, surfaced aggregate failures, and made on-access enforcement explicit |
| Blind map and annotator cards shared one run directory | Moved them to separate private evaluator and annotator roots; cryptographic blinding is still not claimed |
| Private storage could be redirected through links or junctions | Added root, component, artifact, and tombstone link/junction checks with fail-closed path resolution |
| The deletion and replay output overstated its evidence | Renamed the result as a disposable canary and changed replay to a second disk read |
| A focus event did not explicitly require unattributed user-turn authority | Added the invariant to the evidence-window validator |
| The first repeat mismatch could disappear before a receipt existed | Made the initial submission and raw agreement immutable, with mismatches resolved only through a separate adjudication artifact |
| Context digests were accepted without recomputing them from the supplied text | Bound evaluation and history digests to the exact text in model validation |
| Expiry did not cover every read and tombstones had no bounded retention | Enforced on-access purge before store reads and gave tombstones the same seven-day boundary |
| Public research exposed corpus-dependent exact counts | Removed those values; only protocol-fixed cardinalities and categorical pass/fail evidence remain public |
| Deletion closure checked only the control directory | Extended absence checks across control, annotator, and evaluator run roots, including unindexed remnants |
| A crash or concurrent submission could leave unindexed files that a retry overwrote | Added exclusive-create writes, one opaque per-study transaction lock, and index-to-disk inventory validation; interrupted state now fails closed |
| Purge could delete indexed files while an unindexed same-run artifact survived | Required pre-delete inventory equality and post-delete absence across all three scoped roots; incomplete closure is a purge failure |
| The final seal did not identify its adjudication artifact | Added a mandatory adjudication-set digest whenever any repeat pair is adjudicated |
| A corpus-dependent annotation partition count remained public | Replaced it with a categorical configured-bounds result |
| A post-index verification failure could delete payloads while leaving the new index | Restore the prior mutable index before cleanup; if rollback itself fails, preserve committed payloads and report incomplete rollback |
| Draft and ancestor races were not covered end to end | Bind the exact draft-byte digest under lock, verify every immutable entry on index read, and replay the initial and adjudication ancestry with barrier and forged-index tests |

## Remaining Gate

The represented user must complete and submit the 32 blind annotation labels.
That first submission is immutable; any mismatched repeat pairs must then be
resolved in the separate adjudication draft before the final label set seals.
Only afterward may the protected holdout dialogue be opened, exact duplicates checked, target-free
predictions frozen, and represented-user holdout targets collected for scoring.

No real zero-, low-, or history-data quality result exists yet. The installed
local model remains disabled until deterministic baselines have frozen real
predictions. Background deletion scheduling, stronger evaluator access
separation, schema or database persistence, model downloads, and full-corpus
processing remain separate approval boundaries.

## Implementation Pointers

- [`../src/ynoy/persona_study/holdout.py`](../src/ynoy/persona_study/holdout.py)
- [`../src/ynoy/persona_study/labels.py`](../src/ynoy/persona_study/labels.py)
- [`../src/ynoy/persona_study/baselines.py`](../src/ynoy/persona_study/baselines.py)
- [`../src/ynoy/persona_study/source.py`](../src/ynoy/persona_study/source.py)
- [`../src/ynoy/persona_study/artifacts.py`](../src/ynoy/persona_study/artifacts.py)
- [`../tests/test_persona_holdout.py`](../tests/test_persona_holdout.py)
- [`../tests/test_persona_study_labels.py`](../tests/test_persona_study_labels.py)
- [`../tests/test_persona_baselines.py`](../tests/test_persona_baselines.py)
