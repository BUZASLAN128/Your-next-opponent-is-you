# Mathematical Foundation

> Runtime status update, 2026-07-18: the 40-test deterministic and synthetic
> handoff is implemented. See the
> [V1.8 conformance record](../v1-8-runtime-record-2026-07-18.md). Numeric
> calibration, real authentication, universal erasure, timing privacy, and
> persona quality remain unproved.

> Date: 2026-07-17
> Status: research specification; not an implemented architecture or a proof
> of persona fidelity
> Authority: none beyond the already confirmed product and safety constraints

This directory expresses the current YNOY hypothesis as a falsifiable
mathematical contract. Its purpose is not to make the project look scientific.
It is to expose hidden assumptions, identify quantities that must be measured,
and make unsafe state transitions impossible to hide behind prose.

Mathematics does not rescue false premises. A precise equation can still be
wrong when its variables are unobservable, its labels are contaminated, or its
weights are chosen after seeing the test set. Every equation here therefore has
one of three roles:

- **Invariant:** a hard condition the system must never violate.
- **Candidate model:** a testable representation whose parameters are not yet
  selected.
- **Evaluation definition:** a reproducible measurement for comparing the
  structured core with simpler baselines.

## Documents

- [formal-system.md](formal-system.md): objects, admission gates, memory state,
  internal prediction, gated public judgment, abstention, and authority.
- [decision-semantics.md](decision-semantics.md): query-environment scope,
  typed judgment basis, reviewed subject/layer/key groups, three-valued
  conflict, query-valid supersession, and adoption trust.
- [state-privacy-erasure.md](state-privacy-erasure.md): authorization-bound
  expected-head append, observer-indexed trace noninterference, attested erasure
  universe, future-trace deletion, and private-derivative parameter isolation.
- [evaluation-contract.md](evaluation-contract.md): frozen target-specific
  calibration, deterministic matched-coverage selection, pre-registered
  baselines/clusters, controlled inference, and shift strata.
- [implementation-test-contract.md](implementation-test-contract.md):
  candidate interfaces, ownership boundaries, and mandatory red tests.
- [learning-privacy-evaluation.md](learning-privacy-evaluation.md): append-only
  learning, deletion closure, egress non-interference, and sealed evaluation.
- [privacy-and-falsification.md](privacy-and-falsification.md): privacy
  invariants, repository scan results, failure conditions, and the tests that
  could disprove the current design.

## Central claim

Let `StructuredCore` be the scoped, provenance-bearing model and
$\mathcal{B}_{\mathrm{primary}}$ a baseline set frozen under the same evidence
boundary before sealed outcomes are accessible. The narrow V1 hypothesis is:

$$
H_1(\kappa):\quad
\forall b\in\mathcal{B}_{\mathrm{primary}},\quad
\Delta R_b(\kappa)=
R_{\mathrm{YNOY}}(\kappa)-R_b(\kappa)<-\delta
$$

at the one pre-registered primary matched-coverage point, or under a
pre-registered familywise rule over declared primary points, with the applicable
paired cluster-level confidence bound wholly below $-\delta$. Fatal provenance,
scope, privacy, authority, and temporal-leakage violations must remain zero.
No favorable coverage, baseline, cluster mapping, or tie resolution may be
selected after sealed outcomes are visible. Every required safety stratum must
also satisfy its pre-registered absolute risk ceiling under simultaneous or
familywise-controlled upper bounds. Until the comparison specification,
calibration profile, support minima, $\delta$, stratum ceilings, and interval
procedures are frozen, the result is `not_calibrated/inconclusive`.

## External research used as form, not authority

- Google Research's [preference-based activation steering](https://research.google/pubs/personalizing-llms-with-preference-based-activation-steering/)
  shows how a user preference profile can be represented as controllable
  dimensions. It does not provide YNOY's provenance, adoption, scope, or
  authority rules.
- Google DeepMind's [ReadAgent](https://deepmind.google/research/publications/74917/)
  separates compressed episodic memory from lookup into original evidence. It
  does not establish a personal identity model.
- [Selective classification](https://papers.neurips.cc/paper/7073-selective-classification-for-deep-neural-networks.pdf)
  supplies the risk-coverage language used for abstention.
- [AURC evaluation analysis](https://proceedings.neurips.cc/paper_files/paper/2024/file/047c84ec50bd8ea29349b996fc64af4b-Paper-Conference.pdf)
  motivates keeping AURC diagnostic and using matched-coverage risk as the
  primary comparison.
- [Confidence calibration](https://proceedings.mlr.press/v70/guo17a.html) and
  [distribution shift](https://proceedings.neurips.cc/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html)
  motivate separating ranking scores from calibrated probabilities and
  reporting shift strata.
- [Hyperproperties](https://www.cs.cornell.edu/fbs/publications/Hyperproperties.JCS.pdf)
  and [linearizability](https://www.cs.cmu.edu/~wing/publications/HerlihyWing90.pdf)
  motivate whole-trace privacy and expected-head concurrency contracts.
- [Factor graphs and the sum-product algorithm](https://www.mit.edu/~6.454/www_fall_2002/lizhong/factorgraph.pdf)
  motivate local factors for a global conditional model, while explicitly
  warning that cyclic message passing need not be exact.
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) supplies provenance vocabulary;
  it does not decide whether a claim is true or adopted by the represented
  user.

No model family, graph engine, database, threshold, or weight is selected by
this research note.
