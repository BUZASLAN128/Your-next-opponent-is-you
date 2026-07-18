# Exact Private Authorship Receipt

> Date: 2026-07-18
> Status: implemented, synthetically validated, and applied to one private review
> Authority: represented-user authorship only

## Why This Receipt Exists

The fixed-memory harvester produces user-role excerpts but cannot prove that a
particular excerpt expresses the represented user's own words. User-role text
may still contain quotations, pasted material, imported reports, or dialogue
about another person's position. Operator inspection can improve the selector,
but it is not represented-user ground truth.

The user explicitly confirmed that every card in the current bounded private
review came from their historical conversations. The project needs to preserve
that narrow fact without silently turning historical text into a current
decision or persona rule.

## Bound Object

One receipt binds:

- source-study and harvest-run identities;
- exact checkpoint revision and checkpoint digest;
- manifest, holdout freeze, selector configuration, and review digests;
- the ordered candidate identities and candidate payload digests;
- the prior private artifact-index digest;
- the complete source-dependency set; and
- the represented-user actor plus an all-self authorship vector.

The receipt is stored as a new immutable private evaluator artifact. It does
not modify or seal the existing harvest label template.

## Fail-Closed Rules

The first submission must target the current checkpoint head. An exact retry
returns the existing receipt without a second effect. A retry with different
content conflicts. Wrong source, run, revision, checkpoint, order, candidate,
candidate count, or attribution fails closed. Missing checkpoint ancestry,
tampered immutable artifacts, and ambiguous receipt paths also fail closed.

The submission surface is bounded. It cannot carry arbitrary fields, and the
sealed receipt fixes every authority-bearing field to absent or false.

## Authority Boundary

The receipt proves only that the represented user confirmed authorship for the
bound review surface. It does not prove or assign:

- a decision, correction, preference, belief, or other judgment label;
- the statement's current validity or scope;
- represented-user adoption of an inference;
- persona truth or core eligibility;
- benchmark eligibility or calibration;
- model quality, persona similarity, or prediction accuracy; or
- permission to draft, send, execute, promote, or report an action complete.

No model, provider, database, embedding, migration, or automatic promotion is
part of this path.

## Privacy, Retention, and Deletion

The receipt remains under the existing outside-Git private root. It inherits
the run's expiry, indexed tamper checks, and source-dependency deletion
closure. Public research records describe the contract but omit private text,
paths, identifiers, digests, source dates, and aggregates.

This is not a universal erasure claim. Persistent cross-restart fencing,
independent producer attestation, and backup closure remain separate open
requirements.

## Validation Target

Synthetic tests must demonstrate successful all-self sealing, exact-retry
idempotency, changed-retry conflict, source/run/revision/checkpoint/candidate
binding, order and cardinality checks, partial and mixed-attribution rejection,
tamper detection, retention purge, source-dependency deletion, private-root
enforcement, and zero database/model/provider use.

The private application succeeded and an exact retry preserved one receipt and
the same index head. All authority fields remained absent or false. Neither
success created a semantic decision atom. Exact private identifiers, digests,
paths, and counts remain outside Git.

## Next Gate

Create a separate atomic judgment-review contract for the authorship-confirmed
cards. Freeze the meaning of each label, scope rules, uncertainty state, and
acceptance threshold before collecting labels. Only then may the project
consider decision-atom projection or a proposal-only extractor comparison.
