# Implementation and Test Handoff

> Status: candidate interfaces and mandatory failing tests; no implementation
> or schema change is authorized by this document

## 1. Ownership rule

Deterministic application code owns scope, admission, conflict, adoption,
append concurrency, basis selection, trace capture, and erasure parity. Models
may propose extractions or ranking scores but cannot write these decisions.

The names below are candidate contracts. Before implementation, owners must be
mapped to the current modules and migrations reviewed separately. No new
dependency or storage schema follows from this handoff.

The current base is known to diverge at three safety-critical points: risk
`unknown` is treated as a wildcard, no reviewed `decision_key` exists, and an
ordinary correction receipt can satisfy adoption without the independent
channel defined here. These are blocking red tests, not accepted legacy
semantics.

## 2. Candidate interfaces

| Interface | Required contract | Candidate current owner |
| --- | --- | --- |
| `scope_applies` | Pure evaluation of $\omega_q\models s_c$, including `any` and `unknown` | `src/ynoy/scope.py`; correction narrowing remains a separate caller |
| `ConflictAssessment` | Ternary result plus decision key, claim IDs, evidence, and reason | `src/ynoy/decision_brief.py` and the final core resolver |
| `VerifiedAdoption` | Subject/review/claim/head/channel/challenge-bound receipt | New trusted adapter consumed by `correction.py` and `canonical_admission.py` |
| `CalibrationProfile` | Frozen mapping, target, partitions, versions, strata, status | Benchmark protocol/metrics; runtime consumes but cannot author it |
| `EgressTrace` | Canonical observer-visible logical events | `policy.py`, `reasoner.py`, and the transport/telemetry boundary |
| `ReviewAppend` | Expected-head append with event-level idempotency | `review_application.py` plus the private artifact/event-store owner |
| `ErasureRegistry` | Complete producer registry, closure handlers, parity inventory | `storage/erasure_operations.py` and `storage/erasure_repository.py` |
| `judgment_basis` | Exactly one basis and a machine-readable abstention reason | Final core/output resolver, independent of model response schema |

All interfaces fail closed on unknown enum values, missing bindings, stale
versions, malformed canonicalization, and incomplete provenance.

## 3. Mandatory red tests

These tests must fail before implementation and pass only when the specified
behavior exists.

| Test | Required assertion |
| --- | --- |
| `test_general_scope_applies_to_specific_query` | A general stored scope applies to a specific query; a specific scope does not apply to a general or different query |
| `test_risk_unknown_is_not_high_and_any_is_wildcard` | `unknown` never matches known `high`; explicit `any` matches both |
| `test_minimum_coverage_blocks_easy_case_win` | A system answering one easy case cannot win below frozen case and cluster minima |
| `test_uncalibrated_model_score_cannot_emit_persona` | An uncalibrated model score of `0.99` cannot produce `inferredPersona` |
| `test_unknown_same_key_relation_abstains` | An `unknown` relation inside one reviewed decision key forces Mirror abstention |
| `test_different_keys_do_not_create_false_conflict` | Different labels under different decision keys remain independent |
| `test_adoption_is_bound_and_not_replayable` | Adoption for another subject, review, claim, head, or used challenge is rejected |
| `test_private_state_does_not_change_external_trace` | Changing D1-D5 state leaves the external observer's logical trace identical |
| `test_concurrent_append_has_one_winner_and_retry_is_idempotent` | Two appends at one head yield one winner; exact retry returns the first result; changed payload fails |
| `test_unregistered_private_producer_breaks_erasure_parity` | A new private table or artifact producer absent from the registry fails parity |
| `test_tombstone_blocks_post_delete_derivative` | A retry or delayed worker cannot recreate a deleted source or descendant |

## 4. Required fixtures and oracles

- Scope cases are synthetic Cartesian combinations of person, project, role,
  audience, risk, and time; no private corpus fixture is required.
- Conflict fixtures explicitly carry reviewed decision keys. The oracle never
  infers key equality from embeddings or labels.
- Adoption fixtures use a fake independent verifier with freshness and
  expected-head checks; they do not claim to choose the real authenticator.
- Concurrency tests coordinate two writers at the same expected revision and
  preserve both returned outcomes.
- Trace fixtures compare normalized complete logical traces, including errors,
  retries, logs, and telemetry—not only request bodies.
- Erasure parity inventories every private persistence/artifact producer and
  deliberately adds an unregistered synthetic producer.
- Evaluation fixtures freeze cases, clusters, coverage grid, tie order, and
  versions before scoring.

## 5. Acceptance boundary

Green synthetic tests establish only contract behavior. They do not prove
real authenticator security, database linearizability, external-provider
privacy, backup erasure, unlearning, calibrated persona quality, or adequate
sample size. Those require later integration, live, and sealed-evaluation
evidence under separately approved changes.
