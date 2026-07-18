# Observable-Action Pilot — 2026-07-19

## Objective

Test whether bounded, confirmed historical examples improve prediction of a
later observable user-action category. This is narrower than persona
similarity: it measures a target-free next-action classification task, not
voice, identity, semantic adoption, or general judgment fidelity.

## Confirmed Input Boundary

- **Confirmed decision:** The represented user authorized continued local
  processing and requested an actual falsifiable output.
- **Observed fact:** One private receipt binds represented-user authorship to
  an exact bounded review surface.
- **Observed fact:** The selected examples have distinct event times and the
  chronological history/target split has no source or conversation overlap.
- **Boundary:** Authorship does not establish that every historical statement
  is current, adopted, persona evidence, or safe for core promotion.

Raw content, identifiers, paths, hashes, dates, class counts, predictions, and
behavioral aggregates remain outside Git.

## Frozen Pilot Contract

The exact twelve receipt-bound examples are ordered by event time and opaque
candidate identifier. The earlier half becomes history; the later half becomes
sealed cases. A case contains only response-preceding context and receipts. Its
focus response and target label are held in a separate target object.

The deterministic target vocabulary is:

1. correction;
2. evidence demand;
3. scope change;
4. decision;
5. abstention;
6. outcome feedback.

That order resolves multi-signal ties and is included in the manifest hash.
Two arms use the same pinned local model and identical sealed case order:

- `generic`: response-preceding context only;
- `personalized`: the same context plus the earlier receipt-bound examples.

Predictions are sealed before target scoring. Non-loopback endpoints, missing
local attestation, model identity mismatch, changed case order, target-visible
predictions, repeated execution, source overlap, conversation overlap, and
invalid chronology fail closed.

## Result and Correction

The initial private score showed a directional improvement over the generic
model. A post-run methodological audit then compared that improvement with two
precomputable deterministic controls: history-majority and most-recent-history
prediction.

**Research finding:** The personalized arm did not beat the strongest trivial
control. The original directional result is therefore superseded by
`inconclusive`. The immutable private audit preserves both the original result
and the correction instead of deleting the earlier record.

This is useful negative evidence. It shows that the current packet changes
model behavior, but the observed change is explainable by recency rather than
a structured personal model. The public runtime now requires a personalized
arm to beat generic, history-majority, and history-recent controls before it
can emit `positive_directional`.

## Existing Formal Comparator Excluded

A source audit found that the current formal comparison runtime can accept
coverage inference that is not bound back to the selected cases, arms, support
counts, or frozen baseline artifact. Its bootstrap input also does not yet
prove that it represents the matched selected cases at the stated coverage.
The observable-action result therefore does not use that runtime to claim a
win or confidence interval.

This is an implementation gap, not evidence against the mathematical
contract. Until selection, inference, fatal gates, manifests, support, arms,
coverage, and bootstrap samples share one validated receipt chain, formal
comparison output remains support evidence only.

## What Is Proven

- The exact bounded authored examples can be split chronologically without
  source or conversation overlap.
- The target-free input boundary is executable and hash-bound.
- The same local model can be compared with and without personal history.
- A weak apparent win can be detected and downgraded when a trivial baseline
  explains it.
- No private data, target, prediction, or behavioral aggregate must enter Git.

## What Is Not Proven

- persona similarity or successful imitation;
- stable judgment prediction;
- semantic correctness of the structural signal labels;
- calibration or a deployable confidence threshold;
- advantage over retrieval, static profile, or structured-core systems on a
  sufficiently powered sealed benchmark;
- permission to promote memory, send messages, or execute actions.

## Next Discriminating Experiment

Increase independent chronological support without weakening authorship,
lineage, source-overlap, or target-isolation rules. Freeze at least three
nontrivial controls before prediction: recent action, history majority, and a
target-free lexical retrieval baseline. A structured arm becomes interesting
only when it beats all controls on the same sealed cases and the advantage
survives a predeclared uncertainty calculation.

If more trustworthy authored cases cannot be obtained automatically, the
result must remain inconclusive rather than converting structural user-role
records or model guesses into identity truth.
