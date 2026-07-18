# Formula and Flow Defect Report Review — 2026-07-17

> Status: local source and contract review
>
> Reviewed input: [supplied formula and flow defect analysis](incoming-reports/formula-flow-defect-analysis-2026-07-17.md)
>
> Input authority: none
>
> Scope: research and mathematical handoff only; no runtime, schema, corpus,
> model, dependency, commit, or push change

## Verdict

The supplied report identifies useful statistical, notation, and diagram
cautions, but it is not safe to apply verbatim.

Its diagnosis is stronger than its prescriptions. One proposed scoring repair
is internally inconsistent, the proposed authorization implication points in
the wrong direction, and both replacement flows introduce execution and
retention behavior that V1 forbids. The report also misses defects in the
current formal contract, including incomplete decision-group closure, mixed
ranking and emission thresholds, upstream authority taint, indirect private
parameter influence, and post-hoc selection across coverage points.

## Claim Disposition

| Report claim | Disposition | Reason |
| --- | --- | --- |
| Two fixed raters should not default to Fleiss' kappa | Accepted with scope | Cohen's kappa is the conventional fixed-pair starting point; the label scale, missingness, prevalence, confusion matrix, and error cost still determine the protocol |
| `kappa < 0.80` should not automatically reject a field | Accepted | The number has no project-specific empirical basis and kappa is prevalence-sensitive |
| `H(X)>1.5` is undefined without the variable, alphabet, probabilities, and log base | Accepted | The number has no accepted contract status; normalized entropy still needs a defined distribution and a frozen threshold |
| The narrative `resolve(...)` expression is a defective numeric score | Rejected | Its source explicitly states that it is not a numeric scoring rule |
| Replace `resolve(...)` with the report's linear or log score | Rejected | The example coefficients violate the report's own normalization rule, and a sigmoid does not create calibration |
| Partial-derivative notation is a poor authority invariant | Accepted | Authorization is a deterministic policy boundary, not a differentiable persona function |
| The report's probability or reverse-implication authority formulas are safe replacements | Rejected | They do not express persona noninterference and can make an incomplete grant sufficient for authority |
| JPAF constants and P3 percentages are not universal guarantees | Accepted but already recorded | Both transfer limitations were already present in the source ledger |
| Happy-path-only diagrams can hide failure behavior | Accepted as documentation guidance | A normative diagram should expose fail-closed states; the supplied artifact remains preserved rather than rewritten |
| Add execution, cryptographic delegation, budget leases, and rollback to V1.7 | Rejected | V1 Mirror and Advisor cannot send, execute, promote, or claim action; some external effects are irreversible |
| Preserve a tombstone plus provenance snapshot before classification or deletion | Rejected as stated | Edit, revocation, and erasure are different events; an erasure tombstone may not retain private content or reversible content-derived values |
| W3C PROV requires the proposed control flow | Rejected | PROV supplies a provenance data model, not authorization, concurrency, rollback, or erasure enforcement |

## Confirmed Defects Missed by the Report

### 1. The response gate was basis-blind

The former `formal-system.md` gate used an undefined `mathcal K(q)` and required
personal evidence and calibration for every answer. That conflicts with the
four-basis contract: exact adopted policy is deterministic, generic Advisor can
operate at cold start, and only `inferredPersona` requires a valid calibration
profile.

Merely renaming that set was insufficient: a resolver could omit a conflicting
key and manufacture an empty conflict set. The corrected contract derives the
required groups from a versioned deterministic output-dependency manifest that
models and candidate answers cannot narrow, then applies the calibrated
threshold only to the personal-inference gate.

### 2. The parameter-update prohibition omitted private classes

The former rule mentioned only D2-D3 and then only direct training input. V1 now
forbids D1-D5 and their transformed derivatives from influencing examples,
labels, rewards, summaries, hyperparameters, adapters, activation steering, or
any other model-parameter update. The Bayesian notation in the learning
document is explicitly an external, source-linked, recomputable state estimate
rather than neural-weight training.

Credentials and third-party personal data do not gain a future training route.
A later proposal for D1-D3 would require a new purpose, authority, retention,
deletion, and unlearning decision.

### 3. Pointwise coverage wins could be searched after evaluation

The prior contract froze a coverage grid and described a win at each point but
did not define the overall claim across that grid. V1.7 now requires either one
primary coverage point or a pre-registered familywise rule with declared
required points. A favorable point cannot be selected after sealed outcomes
are visible.

Worst-stratum risk is now indexed by matched coverage. A required stratum below
its frozen support minimum makes the overall safety claim inconclusive rather
than disappearing from the maximum.

### 4. Authority independence needed an upstream taint boundary

Holding an already-built authorization tuple fixed does not prevent persona
state from selecting a different valid tuple before projection. It can also
pass vacuously while V1 capability is always disabled. The corrected invariant
requires persona/model-derived state to change neither trusted tuple selection
nor its fields, and the handoff exercises a pure policy oracle with capability
synthetically enabled without authorizing a product action.

### 5. Ranking and persona-emission thresholds were conflated

The evaluation curve used an uncalibrated ranking score and the personal gate
used a calibrated probability under the same threshold symbol. They are now
separate: $\lambda$ orders diagnostic risk-coverage cases, while
$\tau_{\mathrm{persona}}$ governs a runtime personal inference under an
applicable frozen calibration profile. Ranking alone cannot make an output
deployable.

## Corrected Authority Selector Invariant

The earlier fixed-input version of this section was still incomplete: it held
one preselected tuple constant and therefore did not constrain tuple choice.
Let $\ell_{\mathrm{auth}}$ be trusted identity, resource, grant, control, and
explicitly confirmed request state, and let $h$ contain all persona-, model-,
extractor-, and reasoner-derived state. First require

$$
\forall\ell_{\mathrm{auth}},h_1,h_2:\quad
\mathrm{SelectAuth}(\ell_{\mathrm{auth}},h_1)=
\mathrm{SelectAuth}(\ell_{\mathrm{auth}},h_2)=
\mathrm{SelectAuth}_{T}(\ell_{\mathrm{auth}}).
$$

The trusted selector returns one uniquely request-bound tuple
$\gamma_{\mathrm{auth}}$ or denies on zero/multiple matches. For every selected
tuple and every $h$, only then does
$\pi_{\mathrm{auth}}(\gamma_{\mathrm{auth}},h)=\gamma_{\mathrm{auth}}$ and
$\mathrm{Authorize}(\gamma_{\mathrm{auth}},h)=
\mathrm{Policy}(\gamma_{\mathrm{auth}})$ apply. This prevents persona-derived
state from selecting or populating grant/scope upstream. The future test uses a
pure oracle with synthetic capability to avoid a vacuous pass; V1 action
capability remains disabled.

## Documentation-Only Red-Test Additions

The implementation handoff now requires tests for:

- explicit policy without persona calibration;
- non-personal Advisor behavior at cold start;
- deterministic required-decision-group closure and omission attacks;
- subject/layer/key-bound claims, distinct-pair conflict, and query-valid
  supersession;
- authorization invariance under persona-fit changes;
- authorization-tuple selection and projection taint with a non-vacuous pure
  policy oracle;
- V1-wide no-send, no-execute, no-promote, and no-action-claim behavior;
- stale, future, and rebound review events;
- actor/subject/review/adoption-bound append authorization;
- content-free and non-reversible tombstones;
- current producer-universe attestation and quantified future-trace deletion;
- D1-D5 derivative rejection from every model-parameter update surface;
- target-exact sealed-isolated calibration, deterministic matched selection,
  frozen baselines/clusters, post-hoc coverage selection, unadjusted familywise
  claims, unsupported strata, and pooled suppression of a high-risk stratum;
- separation of internal Mirror candidates from gated public judgments.

These are mandatory future red tests, not claims that runtime behavior exists.

## Primary Source Map

| Local claim | Primary source | Transfer limit |
| --- | --- | --- |
| Fixed-pair nominal agreement | [Cohen 1960](https://doi.org/10.1177/001316446002000104) | Does not choose YNOY labels, threshold, or ground truth |
| Many-rater nominal agreement | [Fleiss 1971](https://doi.org/10.1037/h0031619) | Does not make kappa sufficient or require its use |
| Marginal imbalance can depress kappa despite high raw agreement | [Feinstein and Cicchetti 1990](https://doi.org/10.1016/0895-4356(90)90158-L) | Does not select a replacement metric or YNOY threshold |
| Entropy depends on a probability distribution and log-base unit | [Shannon 1948](https://doi.org/10.1002/j.1538-7305.1948.tb01338.x) | Does not validate entropy as a YNOY promotion rule or choose its threshold |
| JPAF constants are implementation choices in the inspected work | [JPAF](https://arxiv.org/abs/2601.10025) | Does not establish real-user judgment fidelity or universal constants |
| P3 percentages belong to its tested datasets and threat model | [P3](https://arxiv.org/abs/2601.17569) | Does not establish a universal leakage ceiling or permission for external egress |
| Risk and coverage must be read together | [Selective Classification for Deep Neural Networks](https://papers.neurips.cc/paper/7073-selective-classification-for-deep-neural-networks.pdf) | Does not provide persona calibration or a YNOY acceptance threshold |
| Provenance vocabulary and constraints | [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) and [PROV Constraints](https://www.w3.org/TR/prov-constraints/) | Do not provide truth, adoption, authorization, rollback, or erasure closure |

## Remaining Uncertainty

- No numeric coverage, support, effect-size, calibration, or kappa threshold is
  selected.
- The overall coverage protocol must still choose one primary point or one
  familywise decision rule before sealed evaluation.
- The numeric selector tolerance, primary baseline manifest, cluster estimand,
  calibration mapping, and persona-emission threshold remain unselected.
- Absolute per-stratum safety ceilings and their simultaneous error-control
  rule remain unselected.
- The timing and resource-contention privacy observer remains open.
- The real adoption authenticator and administrator-compromise treatment remain
  unselected.
- The producer-universe attestation mechanism and exact recovery/backup boundary
  remain unselected.
- No synthetic document check can establish database linearizability, external-
  provider privacy, backup erasure, unlearning, or real persona quality.

## Decision Consequence

The report is preserved and useful as an adversarial research input, not as
architecture authority. Its validated findings strengthen the technology-
neutral formal contract. Its numeric `resolve` replacement, authority formula,
execution flows, storage prescription, and content-bearing snapshot implication
remain rejected.
