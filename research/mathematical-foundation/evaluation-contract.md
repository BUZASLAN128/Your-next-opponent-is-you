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

`calibrated_probability` is produced only by a frozen profile

$$
\Pi_v=(\mathrm{profileId},T_v,\mu_v,\tau_v,
D_{\mathrm{fit}},D_{\mathrm{valid}},V_v,S_v,
\mathrm{freezeReceipt}),
$$

where $T_v$ fixes the `inferredPersona` basis, requested output and full
decision target, label space, represented-user outcome, horizon, and loss;
$\mu_v$ maps ranking features to a probability;
$\tau_v$ is the runtime emission threshold; $V_v$ binds system, predictor,
extractor, score, and data-manifest versions; and $S_v$ declares applicable
shift strata. A difficulty, fluency, or model self-confidence target is not a
persona-correctness target.

Let $Y_{\mathrm{sealed}}$ be sealed represented-user outcomes and let
`ProfileInfluence` include profile targets, mappings, thresholds, features,
partitions, strata, validation status, and version selection. Profile
construction requires

$$
D_{\mathrm{fit}}\cap D_{\mathrm{valid}}=\varnothing,
\qquad
(D_{\mathrm{fit}}\cup D_{\mathrm{valid}})
\cap D^+(Y_{\mathrm{sealed}})=\varnothing,
\qquad
D^+(Y_{\mathrm{sealed}})\cap
\mathrm{ProfileInfluence}(\Pi_v)=\varnothing.
$$

The profile fingerprint and partitions are registered before sealed labels are
accessible; a timestamp alone is not isolation evidence. Define

$$
p_{\mathrm{cal}}(q;\Pi_v)=\mu_v(r(q),\mathrm{features}_v(q)).
$$

`CalibrationApplicable` is true only when the freeze receipt verifies, the
profile was validated on its disjoint validation partition, and its exact
target, basis, versions, feature schema, and shift domain match $q$ and the
frozen predictor. A model saying `0.99` remains only a `ranking_score` until
all of these conditions hold.

Without an applicable calibration profile, Mirror cannot emit an
`inferredPersona` judgment. It may rank evidence internally and then abstain.

## 2. Selective prediction

Let $r(q)$ be the ranking score and $\lambda$ a frozen ranking threshold used
to construct an evaluation risk-coverage curve. Define

$$
g_\lambda(q)=I[r(q)\ge\lambda]I[\mathrm{hardGates}(q)=1].
$$

Coverage and selective risk are

$$
\kappa(\lambda)=\mathbb{E}[g_\lambda(q)]
$$

and

$$
R(\lambda)=
\frac{\mathbb{E}[\ell(f(q),y)g_\lambda(q)]}
{\mathbb{E}[g_\lambda(q)]},
$$

when coverage is non-zero.

For an operational finite comparison, a frozen specification $\Xi$ binds the
case manifest $\mathcal{Q}_\Xi$, arm and score versions, selector kind,
coverage grid, rounding rule, label-blind tie function, permitted rounding
tolerance, support minima, primary baseline manifest, and cluster manifest.
Let `SelectionInfluence` include case eligibility, hard gates, scores, features,
tie order, selector kind, rounding, and every bound manifest. It must satisfy

$$
D^+(Y_{\mathrm{sealed}})\cap
\mathrm{SelectionInfluence}(\Xi)=\varnothing.
$$

For $N=|\mathcal{Q}_\Xi|$ and target $\kappa$, let

$$
n_\kappa=\mathrm{Round}_\Xi(\kappa N)
$$

and, for a ranking-only arm $A$,

$$
S_{A,\Xi}(\kappa)=
\mathrm{Prefix}_{n_\kappa}
\left(\mathrm{Sort}_{(-r_A(q),\mathrm{Tie}_\Xi(\mathrm{caseId}(q)))}
\{q\in\mathcal{Q}_\Xi:\mathrm{hardGates}_A(q)=1\}\right).
$$

The tie function is a frozen total order independent of labels, input order,
future outcomes, and private identity fields. A point exists only when both
arms select exactly $n_\kappa$ cases, meet the frozen case and cluster minima,
and $|n_\kappa/N-\kappa|\le\epsilon_{\kappa,\Xi}$. Otherwise it is
`comparison_unavailable`.

For selected set $S_A=S_{A,\Xi}(\kappa)$, let
$\mathcal{C}_A=\{c:S_A\cap c\ne\varnothing\}$. The finite estimators are

$$
\begin{aligned}
R_A^{\mathrm{case}}(\kappa)&=|S_A|^{-1}
\sum_{q\in S_A}\ell(f_A(q),y_q),\\
R_A^{\mathrm{cluster}}(\kappa)&=|\mathcal{C}_A|^{-1}
\sum_{c\in\mathcal{C}_A}|S_A\cap c|^{-1}
\sum_{q\in S_A\cap c}\ell(f_A(q),y_q).
\end{aligned}
$$

$\Xi$ freezes exactly one as $R_A(\kappa)$; an empty denominator is unavailable.

A deployability claim uses the arm's frozen runtime emission gate instead of a
top-$n$ selector and supports only coverage points where that unretuned gate
selects exactly the required count. A ranking-only selector can establish a
ranking comparison, never authorization to emit `inferredPersona`.

$\lambda$ orders diagnostic cases; only profile threshold $\tau_v$ under the
runtime hard gates may authorize an `inferredPersona` judgment.

## 3. Primary comparison

For each pre-registered primary baseline $b$, the primary persona comparison
is the risk difference at matched coverage:

$$
\Delta R_b(\kappa)=
R_{\mathrm{YNOY}}(\kappa)-R_b(\kappa).
$$

Before the sealed evaluation, the protocol freezes:

- the coverage grid $\mathcal{K}$;
- one overall-claim rule: either a single primary coverage $\kappa^*$ or a
  familywise rule over a declared primary subset $\mathcal{K}_{\mathrm{primary}}$;
- minimum answered cases and minimum independent frozen clusters per point;
- the loss and tie rule;
- the minimum meaningful risk improvement $\delta>0$;
- bootstrap repetitions, interval level, and random seed derivation;
- inference stochasticity, repeat count, seed policy, and aggregation rule;
- all system, extractor, calibration, and data-manifest versions;
- one named primary baseline, or a required baseline family with a joint
  error-control and pass rule;
- one total case-to-cluster mapping, cluster weighting rule, and estimand.

The primary baseline cannot be chosen from sealed outcomes. It is either named
directly or selected by a frozen rule using development data only. Secondary
baselines are diagnostic unless the pre-registration requires all of them and
controls inference jointly across baselines and coverage points.

A system that cannot reach a coverage point with the frozen minimum cases and
clusters is `comparison_unavailable` there. It cannot win by answering one
easy case. Until the numeric values above are chosen and frozen, the result is
`not_calibrated/inconclusive`.

### 3.1 Overall decision across coverage

A pointwise win is not an overall win. The protocol must freeze exactly one of
these before any sealed target is opened:

1. one primary point $\kappa^*$, with every other point diagnostic; or
2. a primary coverage family $\mathcal{K}_{\mathrm{primary}}$, a simultaneous
   or familywise-error-controlled interval procedure, and a fixed pass rule.

For the single-point protocol and every required primary baseline $b$, the
upper confidence bound $U$ must satisfy

$$
U_{1-\alpha}(\Delta R_b(\kappa^*))<-\delta.
$$

For a conservative all-required-points family rule,

$$
\forall(b,\kappa)\in
\mathcal{B}_{\mathrm{primary}}\times\mathcal{K}_{\mathrm{primary}}:\quad
U^{\mathrm{sim}}_{1-\alpha}(\Delta R_b(\kappa))<-\delta.
$$

Another family pass rule may be proposed, but its error control and required
points must be frozen in advance. Selecting a favorable $\kappa$ after seeing
sealed outcomes is forbidden. Until one overall rule is selected and frozen,
the overall result remains `not_calibrated/inconclusive` even when an
individual point looks favorable.

## 4. Paired cluster inference

Each YNOY-baseline pair is evaluated from the same sealed case manifest. Before labels
are opened, $\Xi$ freezes one total case-to-cluster mapping, its dependency
closure, and case- versus cluster-weighted estimand. Resampling draws whole
clusters under that mapping so dependent cases remain together. Re-clustering
after outcomes, predictions, or errors are visible is forbidden. A point with
fewer than the frozen minimum effective clusters is unavailable. For bootstrap
replicate $j$, calculate $\Delta R_{b,j}(\kappa)$ from the paired arms.
The frozen procedure declares zero-denominator handling. A replicate with no
selected case for either arm is invalid, its rate is reported, and the interval
is unavailable unless the pre-registered minimum valid-replicate and effective-
cluster requirements remain satisfied.

YNOY wins at $\kappa$ only when:

1. both systems satisfy the frozen coverage and sample minima;
2. all fatal provenance, privacy, authority, and target-leakage gates are zero;
3. for every required $b$, the entire controlled confidence interval for
   $\Delta R_b(\kappa)$ lies below
   $-\delta$.

Overlapping zero, an interval crossing $-\delta$, an invalid replicate rate
outside its frozen allowance, or unavailable coverage is
inconclusive. This protocol does not convert statistical uncertainty into a
product claim. An overall win additionally requires the frozen rule in Section
3.1; pointwise results cannot be searched after evaluation.

## 5. Summary metrics

AURC is diagnostic and retained only for legacy comparison because it mixes
ranking quality, base predictor quality, and coverage behavior. AUGRC is a
secondary summary. Neither replaces the primary `risk@matched-coverage`
analysis.

Threshold ties use the total order in $\Xi$; the tie rate is reported. A target
label, future outcome, input order, or post-freeze manifest change may never
decide which tied case is selected.

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
and unavailable points. The maximum observed stratum risk at matched coverage
is reported separately:

$$
R_{\mathrm{worst}}(\kappa)=
\max_{s\in\mathcal{S}_{\mathrm{valid}}(\kappa)}R_s(\kappa).
$$

Pooling strata cannot hide a failed worst case. A calibration profile is
applicable only to the version and shift domain it declares; otherwise the
system abstains or reports `not_calibrated`. Required safety strata and their
support minima are frozen before evaluation. Stratum assignment uses only
pre-prediction manifest fields and cannot inspect targets, errors, or future
outcomes. If a required stratum is
unsupported, it is reported as unavailable and the overall safety claim is
inconclusive rather than silently maximizing over the remaining easy strata.

Comparative improvement does not by itself make a stratum safe. For each
required safety stratum $s$, the protocol must also freeze an absolute
coverage-indexed risk ceiling $\rho_s(\kappa)$ and simultaneous or familywise-
controlled upper bounds before sealed outcomes are opened. An overall safety
win requires

$$
\forall s\in\mathcal{S}_{\mathrm{req}}:\quad
U^{\mathrm{sim}}_{1-\alpha}
(R_{\mathrm{YNOY},s}(\kappa))\le\rho_s(\kappa).
$$

This guardrail is separate from $\Delta R$: beating an unsafe baseline cannot
excuse excessive absolute risk. If the ceilings, required coverage points, or
their error-control rule are not frozen, the overall result remains
`not_calibrated/inconclusive`.

## 7. What this contract cannot establish

The equations do not select thresholds, demonstrate enough cases, validate a
persona, or prove production safety. Those claims require the frozen sealed
experiment and represented-user adjudication.
