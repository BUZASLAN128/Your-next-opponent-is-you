# Evaluation Contract

> Status: pre-registration structure; numeric thresholds remain open

> **Implementation gap:** The reviewed base reports that calibration is absent;
> it does not implement this matched-coverage comparison, cluster bootstrap,
> frozen support minima, or shift-stratified calibration profile. No current
> score may be interpreted as a V1.7 persona result.

## 1. Score types

`ranking_score` orders candidates within one frozen system. It may be a model
logit, self-reported confidence, similarity, or another uncalibrated value.
It is not a probability.

`calibrated_probability` is produced only by a frozen calibration mapping
whose training partition, version, target definition, and applicable shift
strata are recorded. A model saying `0.99` is only a `ranking_score` until that
mapping is validated.

Without an applicable calibration profile, Mirror cannot emit an
`inferredPersona` judgment. It may rank evidence internally and then abstain.

## 2. Selective prediction

Let $r(q)$ be the ranking score and $\tau$ a frozen threshold. Define

$$
g_\tau(q)=I[r(q)\ge\tau]I[\mathrm{hardGates}(q)=1].
$$

Coverage and selective risk are

$$
\kappa(\tau)=\mathbb{E}[g_\tau(q)]
$$

and

$$
R(\tau)=
\frac{\mathbb{E}[\ell(f(q),y)g_\tau(q)]}
{\mathbb{E}[g_\tau(q)]},
$$

when coverage is non-zero.

## 3. Primary comparison

The primary persona comparison is the risk difference at matched coverage:

$$
\Delta R(\kappa)=
R_{\mathrm{YNOY}}(\kappa)-R_{\mathrm{baseline}}(\kappa).
$$

Before the sealed evaluation, the protocol freezes:

- the coverage grid $\mathcal{K}$;
- minimum answered cases and minimum independent source clusters per point;
- the loss and tie rule;
- the minimum meaningful risk improvement $\delta>0$;
- bootstrap repetitions, interval level, and random seed derivation;
- all system, extractor, calibration, and data-manifest versions.

A system that cannot reach a coverage point with the frozen minimum cases and
clusters is `comparison_unavailable` there. It cannot win by answering one
easy case. Until the numeric values above are chosen and frozen, the result is
`not_calibrated/inconclusive`.

## 4. Paired cluster inference

Both systems are evaluated on the same sealed cases. Resampling occurs at the
source or conversation cluster level so dependent cases remain together. For
each bootstrap sample $b$ and coverage $\kappa$, calculate
$\Delta R_b(\kappa)$ from the paired systems.

YNOY wins at $\kappa$ only when:

1. both systems satisfy the frozen coverage and sample minima;
2. all fatal provenance, privacy, authority, and target-leakage gates are zero;
3. the entire confidence interval for $\Delta R(\kappa)$ lies below
   $-\delta$.

Overlapping zero, an interval crossing $-\delta$, or unavailable coverage is
inconclusive. This protocol does not convert statistical uncertainty into a
product claim.

## 5. Summary metrics

AURC is diagnostic and retained only for legacy comparison because it mixes
ranking quality, base predictor quality, and coverage behavior. AUGRC is a
secondary summary. Neither replaces the primary `risk@matched-coverage`
analysis.

Threshold ties use a frozen, label-blind order derived from `case_id`; the tie
rate is reported. A target label or future outcome may never decide which tied
case is selected.

## 6. Calibration and shift strata

Calibration is evaluated separately from ranking with Brier score,
reliability or calibration error, coverage, and selective risk. At minimum,
the sealed report separates:

- chronological future;
- unseen project or topic;
- cold-start or low-evidence context;
- conflict or incomplete-provenance context;
- model and extractor version.

Each stratum reports case and cluster support, coverage, risk, calibration,
and unavailable points. The maximum observed stratum risk is reported
separately:

$$
R_{\mathrm{worst}}=\max_{s\in\mathcal{S}_{\mathrm{valid}}}R_s.
$$

Pooling strata cannot hide a failed worst case. A calibration profile is
applicable only to the version and shift domain it declares; otherwise the
system abstains or reports `not_calibrated`.

## 7. What this contract cannot establish

The equations do not select thresholds, demonstrate enough cases, validate a
persona, or prove production safety. Those claims require the frozen sealed
experiment and represented-user adjudication.
