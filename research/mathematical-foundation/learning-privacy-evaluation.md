# Learning, Privacy, and Evaluation

## 1. Learning and correction

The append-only transition is

$$
M_{t+1}=U(M_t,\Delta_t),
$$

where $\Delta_t$ is a verified source, correction, supersession, outcome, or
deletion event. The transition must preserve prior receipts and create a new
state digest. A later action does not mutate the historical source event.

A probabilistic update of recomputable external structured state may be
represented as

$$
P(\theta\mid D_{1:t})\propto
P(d_t\mid\theta)P(\theta\mid D_{1:t-1}),
$$

but only adopted represented-user evidence may enter $D$. Here $\theta$ is an
external, source-linked state estimate, not a neural-model weight, adapter, or
activation-steering parameter. This candidate equation grants no
`TrainingInput` authority. Model-generated text and external documents remain
context or quarantined proposals, and the V1 D1-D5 direct-and-derivative
parameter-update prohibition is normative in
[State, Privacy, and Erasure](state-privacy-erasure.md#4-parametric-memory-prohibition).
The system must not learn identity from its own previous output.

Every durable correction uses the authorization-context-bound expected-head
event defined in
[State, Privacy, and Erasure](state-privacy-erasure.md#1-linearizable-review-append).
That canonical owner defines authorization, idempotency, stale-head, rebound-
context, and concurrent-writer behavior; this overview does not duplicate a
weaker tuple.

## 2. Deletion closure

Let $a\rightarrow b$ mean that artifact $b$ derives from artifact $a$. For a
source $s$, the deletion closure is

$$
D^+(s)=\{s\}\cup\{v:\exists\mathrm{\ path\ }s\rightarrow^+v\}.
$$

A deletion succeeds only when the dependency closure is absent, a current
attestation binds the declared producer universe to its handlers and parity
tests, an erasure receipt verifies, all admissible future traces are independent
of the deleted content, and a tombstone prevents resurrection. The complete
invariant is in [State, Privacy, and Erasure](state-privacy-erasure.md#3-erasure-registry).

## 3. Privacy and egress

For data class $d$ and destination $z$, V1 permits adapter egress only when

$$
\mathrm{Egress}(d,z)=I[d=D0]I[z\in\mathcal{Z}_{\mathrm{allowed}}].
$$

For an external observer $o$, private noninterference requires

$$
\pi_o(\mathrm{Trace}(P,\ell,h_1))
=
\pi_o(\mathrm{Trace}(P,\ell,h_2)).
$$

The trace includes destination, model, payload digest and size, allowed header
classes, call order and count, retries, error paths, logs, and telemetry.
Request-byte equality alone is insufficient. See
[State, Privacy, and Erasure](state-privacy-erasure.md#2-observer-indexed-noninterference).

## 4. Temporal evaluation

For development and sealed dependency clusters,

$$
\max_{i\in\mathcal{D}}\tau_i
<
\min_{j\in\mathcal{S}}\tau_j
$$

and

$$
\mathrm{Clusters}(\mathcal{D})
\cap
\mathrm{Clusters}(\mathcal{S})=\varnothing.
$$

The predictor may see no hidden target, future correction, later outcome, or
derivative of the sealed event.

The primary score is a vector rather than an arbitrary weighted sum:

$$
J=(L_{\mathrm{decision}},L_{\mathrm{calibration}},
L_{\mathrm{scope}},L_{\mathrm{provenance}},
L_{\mathrm{privacy}},L_{\mathrm{promotion}},C_{\mathrm{review}}).
$$

A structured model supports the thesis only if it beats every pre-registered
primary baseline at operationally matched coverage while all fatal-gate counts
remain zero. The frozen selector, case/baseline/cluster manifests, primary risk
difference, paired cluster bootstrap, calibration isolation, shift strata, and
inconclusive status are defined in
[Evaluation Contract](evaluation-contract.md). Numeric values remain open.
