# V1.8 Formal Runtime Conformance Record

> Date: 2026-07-18
> Status: implemented deterministic and synthetic contract checkpoint
> Scientific status: persona quality remains unmeasured and inconclusive

## Authorized Scope

The user authorized the V1.8 plan to move the reviewed mathematical safety
contract into the existing V1 feature branch. The change was limited to:

- completing and freezing the already-started corpus/vault package;
- integrating the separately reviewed mathematical research commits;
- deterministic decision, adoption, append, authorization, egress, erasure,
  and evaluation contracts;
- synthetic fixtures plus the existing disposable loopback PostgreSQL test
  database;
- research records, deterministic bundle generation, and the existing draft
  pull request.

No new dependency, formal-runtime migration, model download, provider call,
real authenticator, personal database migration, automatic promotion, action
authority, or merge was authorized or performed.

## Implemented Boundaries

### Decision and output

- Stored general scope applies to a matching specific query; specific scope
  does not broaden. Risk `any` is the only wildcard and `unknown` matches only
  `unknown`.
- A formal claim identity binds claim ID, subject, target layer, reviewed
  decision key, immutable claim tuple, and receipt digests.
- Conflict is ternary and evaluated only between distinct active claims in one
  full decision key. Missing same-key assessment is unsafe.
- Supersession requires a query-applicable, same-key, receipt-bound successor.
  Missing, mismatched, expired, or cyclic relationships cannot hide a claim.
- Internal ranking candidates and public judgments are different types.
  Uncalibrated scores cannot emit `inferredPersona` or populate confidence.
- Public output basis is one of `explicitPolicy`, `inferredPersona`,
  `genericAdvisor`, or `abstention`. All V1 action capability fields remain
  false and reasoner action-completion prose is not echoed.

### Adoption, append, authorization, and egress

- The synthetic independent verifier binds adoption to subject, review, claim
  tuple, full key, expected head, channel, and one-use challenge.
- It accepts D0 only. Private adoption fails closed because no real
  authenticator has been selected.
- The in-memory append proof enforces expected revision, exact tuple
  idempotency, one winner at a shared head, recorded-policy retry validation,
  and actor/subject/review/adoption authorization binding.
- Authorization projects only one exact trusted tuple. Zero or multiple
  matches deny, and persona/model state is outside the projection input.
- V1 private state projects to no external call trace. The normalized trace
  type nevertheless reserves target, model, payload class and size class,
  permitted header classes, sequence, retry, error, log, and telemetry fields.

### Erasure and parameter isolation

- The registry explicitly enumerates every table created by migrations 001–006
  plus current private artifact producer classes. A new unregistered producer
  breaks parity.
- A synthetic producer-universe attestation binds registry version, producer
  set, handler manifest, and validity revision. It is not a real attestor.
- The synthetic fence blocks retry, import, restore, recovery, and later
  derivation after deletion without retaining content or a content digest.
- Runtime erasure now reports only `local_database_deleted` or `partial` and
  always reports `universal_success=false`.
- D1–D5 and direct or transformed label, reward, summary, selector,
  hyperparameter, adapter, or steering inputs cannot authorize a V1 parameter
  update. V1 performs no parameter update.

### Evaluation

- `CalibrationProfile` separates ranking score from calibrated probability and
  binds an exact output target, represented-user outcome, predictor, extractor,
  feature schema, strata, disjoint partitions, mapping, threshold, and receipt.
- `ComparisonSpec` hash-freezes cases, tie order, dependency closure, primary
  baseline, total cluster mapping, selector, coverage grid, support minima,
  finite risk estimand, primary or familywise rule, effect and absolute-risk
  limits, bootstrap configuration, and required shift strata.
- Matched selection is deterministic and label-blind. Unsupported counts,
  inadequate case or cluster support, mutable manifests, missing primary
  evidence, pointwise evidence under a familywise rule, missing strata, and a
  supported unsafe stratum cannot produce a win.
- The paired cluster bootstrap is seeded only by the frozen specification.
  Runtime supplies no default acceptance numbers or baseline winner.

## Checkpoints

| Commit | Evidence boundary |
| --- | --- |
| `ad0da86` | Bounded corpus/vault ingestion package and disposable integration |
| `750a41f`, `193b582` | Reviewed mathematical contract and closure handoff |
| `a5575c6` | Scope, identity, conflict, supersession, and judgment basis |
| `4c14996` | Adoption, append, authorization, egress, and no-action boundary |
| `f1f5b2f` | Erasure registry, honest deletion status, fence protocol, and parameter isolation |
| `e021fc8` | Frozen matched-coverage, finite-risk, bootstrap, and shift evaluation |

Each runtime checkpoint was committed only after its focused checks and full
repository gates passed, then sent by non-force push to the existing feature
branch and draft pull request. The research-only branch was not pushed.

## Validation Evidence

The final runtime checkpoint passed:

- Ruff lint and formatting checks;
- strict mypy over 164 source files;
- Python compilation for source, tests, and scripts;
- the repository source modularity gate;
- all 40 mandatory formal test names with zero missing;
- 498 tests passed and one environment-qualified test skipped;
- 85.46 percent measured branch coverage against the 70 percent regression
  floor;
- Git whitespace validation.

Database integration used only the disposable loopback `ynoy_test` database.
The personal `ynoy` database was not migrated. No model or provider was called
by the formal contract tests.

## What This Proves

The checkpoint proves deterministic contract behavior under synthetic inputs
and the existing disposable integration environment. It proves that the
implemented gates fail closed for the tested scope, identity, conflict,
adoption, concurrency, authorization, trace, erasure, and evaluation cases.

## What This Does Not Prove

It does not prove:

- that a persona resembles or improves on the represented user;
- calibration on real decisions;
- adequate sample size, thresholds, baselines, or shift ceilings;
- a secure real authenticator or independent producer attestor;
- database linearizability of a future persistent append store;
- cross-restart tombstone enforcement, backup erasure, or unlearning;
- timing or resource-side-channel noninterference;
- real provider privacy or real-corpus completeness;
- automatic promotion, external sending, tool execution, or product readiness.

Until those separate gates exist, persona results remain
`not_calibrated/inconclusive`, private adoption remains unavailable, and
erasure remains a local or partial result rather than a universal claim.
