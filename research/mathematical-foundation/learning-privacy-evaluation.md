# Learning, Privacy, and Evaluation

## 1. Learning and correction

The append-only transition is

$$
M_{t+1}=U(M_t,\Delta_t),
$$

where $\Delta_t$ is a verified source, correction, supersession, outcome, or
deletion event. The transition must preserve prior receipts and create a new
state digest. A later action does not mutate the historical source event.

A probabilistic parameter update may be represented as

$$
P(\theta\mid D_{1:t})\propto
P(d_t\mid\theta)P(\theta\mid D_{1:t-1}),
$$

but only adopted represented-user evidence may enter $D$. Model-generated text
and external documents remain context or quarantined proposals. The system
must not learn identity from its own previous output.

## 2. Deletion closure

Let $a\rightarrow b$ mean that artifact $b$ derives from artifact $a$. For a
source $s$, the deletion closure is

$$
D^+(s)=\{s\}\cup\{v:\exists\text{ path }s\rightarrow^+v\}.
$$

A deletion succeeds only if every member of $D^+(s)$ is absent from active
storage, the source is no longer retrievable, and a non-content-bearing audit
receipt remains. A deletion plan that removes only the source file is not a
valid closure proof.

## 3. Privacy and egress

For data class $d$ and destination $z$, V1 permits adapter egress only when

$$
\operatorname{Egress}(d,z)=I[d=D0]I[z\in\mathcal{Z}_{\mathrm{allowed}}].
$$

For an external adapter, private non-interference requires

$$
\operatorname{Request}_{\mathrm{external}}(D0,D_{1:5})
=\operatorname{Request}_{\mathrm{external}}(D0,\varnothing).
$$

In words: adding private identity data must not change bytes sent to an
external provider. If it does, the boundary has failed.

## 4. Temporal evaluation

For development and sealed dependency clusters,

$$
\max_{i\in\mathcal{D}}\tau_i
<
\min_{j\in\mathcal{S}}\tau_j
$$

and

$$
\operatorname{Clusters}(\mathcal{D})
\cap
\operatorname{Clusters}(\mathcal{S})=\varnothing.
$$

The predictor may see no hidden target, future correction, later outcome, or
derivative of the sealed event.

The primary score is a vector rather than an arbitrary weighted sum:

$$
J=(L_{\mathrm{decision}},L_{\mathrm{calibration}},
L_{\mathrm{scope}},L_{\mathrm{provenance}},
L_{\mathrm{privacy}},L_{\mathrm{promotion}},C_{\mathrm{review}}).
$$

A structured model supports the thesis only if it beats simple baselines on
the declared primary measures while all fatal-gate counts remain zero. Weights
may be introduced later only through a recorded decision made before sealed
evaluation.
