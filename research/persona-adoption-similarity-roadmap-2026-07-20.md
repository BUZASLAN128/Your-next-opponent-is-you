# Persona Adoption and Similarity Roadmap — 2026-07-20

## Objective and Authority Boundary

Advance the receipt-bound temporal persona into a falsifiable personal
executive agent. The user's delegated sequencing authority permits evidence
ranking, system recommendations, private shadow simulation, reversible
engineering choices, and frozen experimental defaults. It does not permit an
assistant or model to impersonate the represented user or author
`VerifiedAdoption`.

When personal evidence is missing, the runtime may use generic Advisor ability
with the personal basis marked unknown. It may not act as though an invented
fact was observed, remembered, current, scoped, or user-approved.

## Phase 1 — Deterministic System Adjudication

**Status:** In implementation.

Build a package-bound adjudication profile over the retained temporal artifact:

- high-repetition direct evidence becomes a shadow-simulation hypothesis;
- repeated direct evidence becomes a review priority;
- weak repetition waits for more evidence; and
- every unscoped contextual transition waits for scope review.

The profile must report source totals, represented recommendations, omissions,
and whether the projection is complete. All dispositions remain
`user_adoption=not_provided`, `currentness_status=not_established`,
`semantic_adoption=not_established`, `core_eligible=false`, and
`authority=none`.

**Owning paths:** `src/ynoy/models/persona_adjudication.py`,
`src/ynoy/full_persona/persona_adjudication.py`, package model/builder, package
CLI handler, and adjudication/package tests.

**Completion signal:** hashes and exact candidate targets reconcile; overflow
is visible; no current responder consumes the recommendations; synthetic and
private runs emit only content-free aggregates.

## Phase 2 — Lossless Recommendation and Review Ledger

Keep the active evolution profile bounded, but never omit candidates from the
review inventory. Write immutable 64-candidate pages and a final manifest that
binds pack, evolution source, ordered candidate identifiers, page hashes,
totals, and the previous review head. A complete manifest is valid only when
derived, indexed, and paged totals agree.

**Owning paths:** `src/ynoy/models/persona_evolution_review.py`,
`src/ynoy/full_persona/persona_evolution_candidates.py`,
`src/ynoy/full_persona/persona_evolution_review.py`,
`src/ynoy/full_persona/persona_evolution_review_store.py`, a narrow study CLI
handler, and storage/replay/deletion tests.

**Completion signal:** every derived candidate is accounted for; exact retry is
idempotent; partial, reordered, stale, cross-pack, or cross-head input fails
closed. Hitting a byte, time, or page bound aborts without a completeness claim.

## Phase 3 — Target-Free Shadow Simulation

Add a `ShadowPersonaContext` that can consume only
`simulate_as_hypothesis`. Compare generic Advisor, static candidate context,
and temporal candidate context with the same query, model identity, decode
settings, context budget, and no-action output schema.

The projection preserves receipts and exposes
`basis=unvalidated_persona_simulation`. Missing or conflicting evidence causes
Advisor fallback or abstention. Simulation cannot enter memory, adoption,
policy, authorization, or completed-action records.

**Owning paths:** `src/ynoy/models/persona_snapshot.py`,
`src/ynoy/full_persona/temporal_projection.py`, persona response models,
`response_context.py`, `response_protocol.py`, `responder.py`, and focused
target-isolation/equal-budget tests.

**Completion signal:** synthetic scenarios prove deterministic selection,
target isolation, equal budgets, generic fallback, and zero persistence or
authority.

## Phase 4 — Represented-User Adoption Channel

**Status:** Cryptographic local challenge protocol and in-memory append gate
implemented; interactive credential enrollment and the persistent lossless
candidate-review ledger remain pending.

The private atomic review records disposition, explicit scope, currentness,
exact adopted statement, supersession, and whether a transition is a genuine
change, context switch, temporary exception, or unsupported. The original
evidence candidate remains immutable.

A real authenticator binds actor, subject, review, exact candidate tuple,
decision key, stream, event, payload, expected head, channel, credential,
freshness, and response. The dependency-free local implementation delegates
signing to system OpenSSH with a separately entered non-empty key passphrase
and verifies the signature under a dedicated namespace. Challenge and used-
receipt state survive restart; exact replay and implicit credential replacement
fail closed. Challenges expire in at most five minutes, their state envelope is
bound to the enrolled profile, and the append gate rechecks actor, subject,
review, head, stream, event, and payload. This is local key possession and
intent under the V1 trusted-OS-user boundary, not protection from administrator
compromise or a durable multi-process append ledger.

Windows WebAuthn/platform-passkey signing remains a stronger future candidate
for hardware-backed user verification. `UserConsentVerifier` alone is not an
acceptable replacement because it returns a local result enum rather than a
signature over the canonical challenge.

**Owning paths:** new evolution-adoption model/builder/store modules plus
`adoption.py`, `formal_runtime.py`, `review_append.py`,
`canonical_admission.py`, and replay/conflict/erasure tests.

**Completion signal:** assistant output, repetition, a hash, a CLI flag, or a
model response cannot create adoption. Wrong subject, candidate, scope, review,
channel, nonce, or head fails closed.

## Phase 5 — Sealed Persona-Similarity Evaluation

Only prospective cases collected after the adopted snapshot/evidence cutoff,
or targets independently sealed before candidate derivation, are acceptance-
eligible. The current full-history profile cannot support a retrospective win.

Freeze generic, majority, recency, retrieval, static-reviewed, and temporal-
reviewed arms before targets. Predictions freeze before target answers or
blind represented-user ratings open. A model judge is diagnostic only.

Lexical reproduction is an exclusion diagnostic, never similarity credit. A
content-free audit records exact-copy cases and maximum source n-gram
containment per arm. A structured response above the frozen contamination
limit makes the run contaminated or inconclusive even when its decision label
matches. Source hashes are derived from their exact text. Caller-authored
`authenticated`, `sealed`, `prospective`, or `target_isolated` booleans are not
proof; protocol 0.1 therefore keeps every label set `proxy_only` until a signed
rating receipt and independently verified freeze artifact are integrated.

**Owning paths:** new persona-similarity model, split, runtime, scoring, artifact
store, CLI, security tests, and scoring tests.

**Delegated frozen defaults:** at least 24 scenarios from eight source-disjoint
clusters; at least 18 valid rated three-arm cases; zero critical provenance,
privacy, authority, or false-action violations; temporal paired loss at least
`1/24` better than both static and generic; one-sided 99 percent cluster-
bootstrap upper bound below zero; and no regression in a predeclared supported
high-risk stratum. Otherwise the result is `inconclusive` or `negative`.

**Completion signal:** one receipt chain binds cutoff, cases, clusters, arms,
budgets, model, predictions, targets, user ratings, metrics, and bootstrap
inputs. Thresholds cannot change after target access.

## Phase 6 — Executive-Agent Operating Loop

Project reviewed decision logic into source-bound manager briefs: project
state, decision options, plan, delegation candidates, risks, unknowns,
approvals, expected outcomes, and evidence basis. Drafting remains separate
from sending or execution.

**Owning paths:** new `src/ynoy/executive/` modules, an executive brief model,
`manager.py`, manager CLI handler, and provenance/correction/no-action tests.

**Completion signal:** every proposal is traceable and correctable; unapproved
delegation never executes.

### Maker–Checker Shadow Council

Two agents may improve proposal quality only under asymmetric roles. The maker
produces a candidate; the checker searches for unsupported inference, scope
drift, contradiction, provenance loss, and source copying. Agreement creates
only a `system_consensus_candidate`. Disagreement causes abstention or review.
Neither agent may authenticate the other, create represented-user adoption, or
turn repeated mutual agreement into authority. Evaluation must compare this
two-agent condition against a single-agent control to detect correlated-error
amplification rather than assume independence.

## Phase 7 — Reversible Outcome Learning

For local coding tasks, the model owns the expectation proposal and an
independent Git/test observer owns the outcome receipt. Outcomes may change
ranking or create a `LessonCandidate`, but cannot silently rewrite identity,
policy, mission, or the immutable constitution.

**Delegated efficacy defaults:** 24 prospective tasks across eight dependency
clusters; at least 18 independently verifiable outcomes; loss `0` success,
`0.5` partial, `1` failure, with unverifiable uncovered; at least `1/24` mean-
loss improvement over a frozen no-learning control; one-sided 99 percent
cluster-bootstrap upper bound below zero; no increase in substantive user
corrections; and zero unauthorized or false-success events.

**Owning paths:** new executive outcome model, outcome, learning, and store
modules plus replay, supersession, erasure, and false-success tests.

**Completion signal:** failed proposals change no active state; adopted updates
are independently authenticated, replay-safe, source-deletable, and reversible.
This is bounded learning, not an AGI or self-authority claim.

## Compatibility and Rollback

Package `0.3` is a new immutable artifact. Existing `0.2` packages remain
untouched and cannot enter adjudication until rebuilt. Before review activation,
add explicit legacy classification: `0.2` may be inspected as
`adjudication=absent` but cannot be silently upgraded or reviewed. Rebuild
creates `0.3` and atomically advances the latest pointer.

Code rollback reverts the adjudication checkpoint and restores the previous
reader. Adoption, revocation, correction, and learning changes are append-only
supersession events. Sealed experiments are never edited; protocol or threshold
changes create new manifests.

## Validation and Stop Conditions

Each checkpoint requires focused tests, touched-file compilation, Ruff, mypy,
full pytest with branch coverage at least 70 percent, source limits,
deterministic research bundle generation, Git diff inspection, and a private-
data leakage scan.

Stop on unreconciled candidate totals, missing independent user presence,
changed source/package/head after challenge issuance, unresolved scope or
currentness at adoption, target leakage, unequal arm budgets, model identity
failure, non-human acceptance ratings, model-asserted outcomes, private artifact
egress, automatic promotion, action execution, dependency/migration changes,
force push, or merge without separate approval. Conflict causes abstention;
an inconclusive result is never tuned away after target access.
