# Mathematical Foundation

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
  prediction, abstention, and authority.
- [learning-privacy-evaluation.md](learning-privacy-evaluation.md): append-only
  learning, deletion closure, egress non-interference, and sealed evaluation.
- [privacy-and-falsification.md](privacy-and-falsification.md): privacy
  invariants, repository scan results, failure conditions, and the tests that
  could disprove the current design.

## Central claim

Let `StructuredCore` be the scoped, provenance-bearing model and `Baseline` be
the best simpler arm available under the same evidence boundary. The narrow V1
hypothesis is:

$$
H_1:\quad
R_{\mathrm{sel}}(\text{StructuredCore})
< R_{\mathrm{sel}}(\text{Baseline})
$$

subject to zero fatal provenance, scope, privacy, authority, and temporal-
leakage violations. Lower prediction error without those constraints does not
support the product thesis.

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
- [Factor graphs and the sum-product algorithm](https://www.mit.edu/~6.454/www_fall_2002/lizhong/factorgraph.pdf)
  motivate local factors for a global conditional model, while explicitly
  warning that cyclic message passing need not be exact.
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) supplies provenance vocabulary;
  it does not decide whether a claim is true or adopted by the represented
  user.

No model family, graph engine, database, threshold, or weight is selected by
this research note.
