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
| `CanonicalClaimIdentity` | Stable claim and subject IDs plus a receipt-bound subject/layer/decision key | Canonical admission owner; models may propose but cannot establish it |
| `RequiredDecisionGroups` | Versioned deterministic closure over active full-key groups that no model or candidate output can narrow | Final core/output resolver plus a system-control manifest owner |
| `ConflictAssessment` | Ternary result over distinct active claim IDs plus full key, evidence, and reason | `src/ynoy/decision_brief.py` and the final core resolver |
| `VerifiedAdoption` | Subject/review/immutable-claim/full-key/head/channel/challenge-bound receipt | New trusted adapter consumed by `correction.py` and `canonical_admission.py` |
| `CalibrationProfile` | Frozen exact target, mapping, threshold, disjoint partitions, versions, strata, and receipt | Benchmark protocol/metrics; runtime consumes but cannot author it |
| `ComparisonSpec` | Frozen case, selector, coverage, primary baseline, cluster, support, and inference manifests | Benchmark protocol owner; sealed outcomes cannot mutate it |
| `EgressTrace` | Canonical observer-visible logical events | `policy.py`, `reasoner.py`, and the transport/telemetry boundary |
| `ReviewAppend` | Authorized actor/subject/review/adoption context plus expected-head idempotency | `review_application.py` plus the private artifact/event-store owner |
| `AuthorizationSelector` | Unique-or-deny trusted request binding independent of all model/persona state | Policy owner before the authorization oracle |
| `ErasureRegistry` | Attested producer universe, bound handlers, closure receipt, and parity inventory | `storage/erasure_operations.py` and `storage/erasure_repository.py` |
| `judgment_basis` | Disjoint internal candidate and public tagged union with machine-readable abstention | Final core/output resolver, independent of model response schema |

All interfaces fail closed on unknown enum values, missing bindings, stale
versions, malformed canonicalization, and incomplete provenance.

## 3. Mandatory red tests

These tests must fail before implementation and pass only when the specified
behavior exists.

| Test | Required assertion |
| --- | --- |
| `test_general_scope_applies_to_specific_query` | A general stored scope applies to a specific query; a specific scope does not apply to a general or different query |
| `test_risk_unknown_is_not_high_and_any_is_wildcard` | `unknown` never matches known `high`; explicit `any` matches both |
| `test_canonical_claim_requires_subject_and_reviewed_decision_key` | Missing or mismatched subject, model-only key, wrong target layer, or receipt rebinding fails admission and cannot enter persona evidence |
| `test_minimum_coverage_blocks_easy_case_win` | A system answering one easy case cannot win below frozen case and cluster minima |
| `test_uncalibrated_model_score_cannot_emit_persona` | An uncalibrated model score of `0.99` cannot produce `inferredPersona` |
| `test_persona_calibration_profile_is_frozen_and_target_exact` | A profile for another requested output, full decision target, outcome, basis, predictor, version, feature schema, or stratum cannot authorize persona emission |
| `test_sealed_labels_cannot_influence_calibration_profile_or_threshold` | Sealed outcomes and derivatives cannot affect profile mapping, threshold, target, features, partitions, strata, or version selection |
| `test_explicit_policy_does_not_require_persona_calibration` | One exact, applicable, unambiguous adopted policy may produce `explicitPolicy` without a persona calibration profile |
| `test_generic_advisor_remains_nonpersonal_at_cold_start` | With no personal evidence, Advisor may return generic advice but cannot label it as the user's likely choice |
| `test_internal_mirror_candidate_is_not_a_public_output_type` | Internal `MirrorCandidate` cannot serialize or type-check as any `PublicJudgment` variant |
| `test_mirror_argmax_cannot_bypass_basis_gate` | A high-scoring internal candidate with a failed persona gate yields abstention, never an inferred public judgment |
| `test_mirror_argmax_tie_uses_frozen_label_blind_order` | Equal-probability labels resolve through the frozen predictor tie rule, independent of input order, targets, and model prose |
| `test_unknown_same_key_relation_abstains` | An `unknown` relation inside one reviewed decision key forces Mirror abstention |
| `test_conflict_requires_two_distinct_active_claims` | A singleton cannot conflict with itself; missing assessment for two distinct active same-key claims is `unknown` and abstains |
| `test_supersession_requires_active_applicable_same_subject_key` | Wrong-subject/key/layer, revoked, expired, future, out-of-scope, cyclic, unresolved, or unbound supersession cannot suppress an active claim |
| `test_required_decision_group_omission_abstains` | A missing, stale, unresolved, or deliberately narrowed dependency manifest cannot omit a relevant conflicting key to produce persona output |
| `test_different_keys_do_not_create_false_conflict` | Different labels under different decision keys remain independent |
| `test_persona_fit_never_changes_authorization` | With a pure policy oracle and synthetic capability enabled, changing any persona-derived state changes neither projected grant/scope fields nor allow/deny; every missing trusted gate still denies |
| `test_persona_state_cannot_taint_authorization_projection` | Direct and transformed persona/model values cannot populate or alter capability, grant, scope, confirmation, audit, or kill-safety inputs |
| `test_persona_state_cannot_select_authorization_tuple` | With competing trusted tuples, changing model/persona state changes neither tuple identity nor fields; zero or multiple trusted matches deny |
| `test_v1_never_sends_executes_promotes_or_claims_action` | Every basis, error, retry, and fallback path leaves send, execute, promote, and action-claim capability disabled |
| `test_adoption_is_bound_and_not_replayable` | Adoption for another subject, review, claim, head, or used challenge is rejected |
| `test_private_state_does_not_change_external_trace` | Changing D1-D5 state leaves the external observer's logical trace identical |
| `test_concurrent_append_has_one_winner_and_retry_is_idempotent` | Two appends at one head yield one winner; exact retry returns the first result; changed payload fails |
| `test_append_rejects_stale_future_and_rebound_event` | Stale or future heads fail; reusing an event ID with another stream, type, causation, expected revision, or payload fails |
| `test_review_append_requires_trusted_bound_authorization_context` | An untrusted actor, unequal inner/outer context, or mismatched subject, review, stream, event policy, or required adoption reference cannot append |
| `test_review_append_retry_binds_actor_subject_review_and_adoption_context` | A new event uses current policy; an exact retry verifies its recorded policy/receipt, creates no second effect, and may return only its non-content acknowledgement; rebound context, invalid receipt, or unauthenticated retry denies without revealing ID existence |
| `test_unregistered_private_producer_breaks_erasure_parity` | A new private table or artifact producer absent from the registry fails parity |
| `test_erasure_requires_current_bound_producer_universe_attestation` | Missing, self-declared, stale, or version-mismatched universe attestation prevents deletion success |
| `test_post_delete_independence_covers_admissible_future_traces` | Counterfactual deleted contents produce identical judgments, retrieval, derivation, logs, telemetry, and calls under every admitted retry/import/restore/recovery schedule |
| `test_tombstone_blocks_post_delete_derivative` | A retry or delayed worker cannot recreate a deleted source or descendant |
| `test_tombstone_contains_no_private_or_reversible_derivative` | A tombstone contains neither deleted content, private metadata, embeddings, behavior aggregates, nor reversible or low-entropy content fingerprints |
| `test_all_private_classes_and_derivatives_cannot_influence_parameters` | D1-D5 and transformed labels, rewards, summaries, selectors, hyperparameters, adapters, and steering artifacts cannot alter a V1 parameter update |
| `test_matched_coverage_selector_is_deterministic_label_blind_and_tolerance_bound` | Input reordering, tied scores, hidden labels, or their derivatives cannot change eligibility, gates, scores, or the frozen top-$n$ set; unsupported counts or rounding tolerance are unavailable |
| `test_matched_coverage_uses_frozen_finite_risk_estimand` | Case- and cluster-weighted estimators produce their declared values; changing the estimand after freeze or encountering an empty denominator makes the comparison unavailable |
| `test_baseline_and_cluster_manifest_cannot_change_after_freeze` | Replacing a baseline, cluster mapping, dependency closure, weighting rule, or selector version after freeze invalidates the comparison |
| `test_posthoc_coverage_selection_cannot_win` | A favorable non-primary coverage point cannot create an overall win after sealed outcomes are visible |
| `test_pointwise_intervals_do_not_satisfy_familywise_rule` | Unadjusted pointwise intervals cannot be relabeled as simultaneous or familywise-controlled evidence |
| `test_missing_required_shift_stratum_is_inconclusive` | A required stratum below frozen case or cluster support makes the overall safety claim inconclusive |
| `test_supported_high_risk_stratum_cannot_be_hidden_by_pooling` | A supported required stratum whose simultaneous upper risk bound exceeds its frozen absolute $\rho_s(\kappa)$ ceiling blocks an overall safety win even when pooled risk and matched-coverage improvement pass |

## 4. Required fixtures and oracles

- Scope cases are synthetic Cartesian combinations of person, project, role,
  audience, risk, and time; no private corpus fixture is required.
- Conflict fixtures explicitly carry subject/layer/decision keys and immutable
  claim-tuple bindings. The oracle never infers key equality from embeddings or
  labels. A versioned dependency
  manifest is frozen before generation, and one adversarial fixture omits a key
  that can change the basis or rationale.
- Basis fixtures separate an unambiguous adopted policy, calibrated persona,
  generic cold-start advice, and abstention. Only the persona case consumes a
  calibration profile.
- Adoption fixtures use a fake independent verifier with freshness and
  expected-head checks; they do not claim to choose the real authenticator.
- Concurrency tests coordinate two authorized writers at the same expected
  revision, preserve both outcomes, and adversarially rebind context fields.
- Trace fixtures compare normalized complete logical traces, including errors,
  retries, logs, and telemetry—not only request bodies.
- Erasure parity uses a version-bound synthetic universe attestation,
  deliberately adds an unregistered producer, and compares future traces under
  retries and recovery. Tombstones are checked against deleted content and
  low-entropy fingerprints, not only raw text.
- Parameter-update fixtures enumerate D1-D5 and transformed derivatives across
  every declared model-update surface; external source-linked structured state
  remains a separate owner.
- Evaluation fixtures freeze cases, exact primary baselines, total cluster
  mapping, selector, coverage grid, rounding tolerance, tie order, and versions
  before scoring. They also freeze one primary coverage or a
  simultaneous or familywise-controlled decision rule and the required shift
  strata before scoring; a pooled pass cannot suppress a supported failing
  stratum.

## 5. Acceptance boundary

Green synthetic tests establish only contract behavior. They do not prove
real authenticator security, database linearizability, external-provider
privacy, backup erasure, unlearning, calibrated persona quality, or adequate
sample size. Those require later integration, live, and sealed-evaluation
evidence under separately approved changes.
