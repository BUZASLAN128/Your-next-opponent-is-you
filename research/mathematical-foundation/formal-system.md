# Formal System Model

> Status: technology-neutral candidate model with hard safety invariants

## 1. State and notation

Let the represented person be $u$, the evaluation time be $t$, and a request be

$$
q=(x,\omega,t,u,m),
$$

where $x$ is task context, $\omega$ is the concrete query environment, $t$ is
evaluation time, $u$ is the represented subject, and $m$ is the operating
mode. The first supported modes are Mirror and Advisor. A mode changes the
objective, never the evidence history or action authority.

One source event is

$$
e_i=(z_i,a_i,h_i,\tau_i,s_i,d_i,r_i),
$$

where $z_i$ is immutable source content or its private reference, $a_i$ is the
observed speaker, $h_i$ is the represented claim holder, $\tau_i$ is event
time, $s_i$ is scope, $d_i$ is data class, and $r_i$ is its source receipt.
Speaker and claim holder are separate variables: a user turn can quote another
person and an assistant turn can describe the user without becoming user
evidence.

An atomic claim candidate is

$$
c_j=(\mathrm{claimId}_j,\mathrm{subjectId}_j,
\mathrm{decisionKey}_j,\ell_j,\iota_j,\mathrm{layer}_j,
s_j,[b_j,e_j],v_j,p_j),
$$

where the first three fields are stable claim, represented-subject, and
user-reviewed decision-question identities. The remaining fields are literal
evidence, interpretation, target layer, scope, validity, lifecycle, and
provenance. The decision-key record also binds its target layer.

The memory state is an event-sourced tuple

$$
M_t=(E_t,C_t,R_t,G_t,A_t),
$$

containing source events, claims, correction receipts, provenance/dependency
edges, and audit receipts. Source events are never rewritten to make a later
interpretation look original.

## 2. Canonical admission gate

A claim may enter represented-user memory only when every hard term is true:

$$
\mathrm{Admit}(c)=
I_{\mathrm{identity}}
I_{\mathrm{key}}
I_{\mathrm{adopted}}
I_{\mathrm{source}}
I_{\mathrm{receipt}}
I_{\mathrm{class}}
I_{\mathrm{status}}.
$$

The indicators mean:

- $I_{\mathrm{identity}}$: the stable subject ID, represented claim holder,
  authenticated adoption actor, and review subject agree;
- $I_{\mathrm{key}}$: one reviewed subject/layer/decision key is receipt-bound
  to the immutable claim tuple;
- $I_{\mathrm{adopted}}$: one fresh, subject/review/claim/head-bound approval
  verifies through the separate adoption channel;
- $I_{\mathrm{source}}$: literal spans still match immutable source evidence;
- $I_{\mathrm{receipt}}$: the complete review and receipt chain verifies;
- $I_{\mathrm{class}}$: data-class transitions are allowed;
- $I_{\mathrm{status}}$: the claim is confirmed and not invalidated;
  query-relative supersession is an active-projection operation.

`Admit(c)` is Boolean and fail-closed, and implies
`retrievableIdentity(c)=1`. Similarity, confidence, recency, or repetition
cannot replace a factor. The unimplemented independent-adoption target and its
hash limitation are defined in
[Decision Semantics](decision-semantics.md#5-verified-adoption-boundary).

## 3. Applicability at query time

Scope is a predicate over the concrete query environment, not a total or
partial ordering between stored and requested scopes:

$$
\mathrm{Applies}(c,q)=
\mathrm{Admit}(c)\,
I[\omega_q\models s_c]\,
I[t_q\in[b_c,e_c]]\,
I[\mathrm{subjectId}(c)=u_q]\,
I[\neg\mathrm{revoked}(c)].
$$

The exact matching semantics, including the distinction between `any`,
`unknown`, and an absent constraint, are normative in
[Decision Semantics](decision-semantics.md#1-query-and-scope).

## 4. Supersession and conflict

Conflict is a total three-valued relation over distinct active claims in one
reviewed decision group. Only an active, applicable, same-subject, same-key,
same-layer reviewed successor may remove a claim from that group. The complete
normative definitions are in
[Decision Semantics](decision-semantics.md#3-three-valued-conflict).

## 5. Relevance without false authority

Eligible claims may be ordered by a candidate feature vector

$$
\rho(c,q)=
(\mathrm{semantic}(c,q),
\mathrm{scopeSpecificity}(c,q),
\mathrm{temporalFit}(c,q),
\mathrm{outcomeSupport}(c),
\mathrm{evidenceQuality}(c)).
$$

No scalar weights are confirmed. A weighted score

$$
R_w(c,q)=w^\top\rho(c,q)
$$

is only a future candidate and must be calibrated on development data without
opening the sealed target set. Ranking affects attention, not admission,
truth, or authority.

## 6. Conditional judgment model

For decision labels $y\in\mathcal{Y}$, a technology-neutral factorization is

$$
P(y\mid q,\mathcal{E})=
\frac{1}{Z(q,\mathcal{E})}
\prod_{k=1}^{K}\phi_k(y,q,\mathcal{E}_k).
$$

The candidate factors satisfy $\phi_k\ge 0$, and the normalizer is

$$
Z(q,\mathcal{E})=
\sum_{y\in\mathcal{Y}}
\prod_{k=1}^{K}\phi_k(y,q,\mathcal{E}_k),
\qquad 0<Z(q,\mathcal{E})<\infty.
$$

Candidate factors may represent explicit decisions, scoped preferences,
mission state, evidence demands, current task context, and contradiction
signals. This factorization is a model description, not a requirement to use a
graph database or belief propagation. If cyclic approximate inference is ever
used, its approximation error must be measured rather than called exact.

## 7. Basis-specific abstention and selective risk

Selection is basis-specific. For a frozen output-contract version $v$, let
$\mathcal{G}_{\mathrm{req}}(q,v)$ be the deterministic dependency closure from
[Decision Semantics](decision-semantics.md#31-required-decision-group-closure).
Define its unresolved group keys as

$$
\mathcal{U}(q)=
\{k\in\mathcal{K}_{\mathrm{req}}(q,v):
\mathrm{UnsafeDecisionGroup}(k,q)=1\}.
$$

$G_k$ and $\mathrm{UnsafeDecisionGroup}$ are defined in
[Decision Semantics](decision-semantics.md#3-three-valued-conflict). This set
is scoped to the decision groups needed by the requested output; an unrelated
conflict under another key does not block it.

Let $f_v(q)$ be an internal predicted personal decision and $\Pi_v$ one frozen
calibration profile for that predictor and output-contract version. Mirror may
emit the `inferredPersona` basis only when
$g_{\mathrm{persona}}(q;\Pi_v)=1$:

$$
\mathrm{PersonaJudgment}(q;\Pi_v)=
\begin{cases}
(\mathrm{inferredPersona},f_v(q)), & g_{\mathrm{persona}}(q;\Pi_v)=1,\\
(\mathrm{abstention},\bot), & g_{\mathrm{persona}}(q;\Pi_v)=0.
\end{cases}
$$

Let $\mathcal{E}_{\mathrm{persona}}(q)$ be the applicable admitted evidence in
the persona target layer. The hard personal-inference gate is

$$
g_{\mathrm{persona}}(q;\Pi_v)=
I[\mathcal{E}_{\mathrm{persona}}(q)\ne\varnothing]
I[\mathcal{U}(q)=\varnothing]
I[\mathrm{provenanceComplete}(\mathcal{E}_{\mathrm{persona}}(q))]
I[\mathrm{scopeSafe}(\mathcal{E}_{\mathrm{persona}}(q),q)]
I[\mathrm{CalibrationApplicable}(\Pi_v,q,f_v)]
I[p_{\mathrm{cal}}(q;\Pi_v)\ge\tau_{\mathrm{persona}}(\Pi_v)].
$$

$\tau_{\mathrm{persona}}$ is not selected yet. A model-provided confidence is
only a ranking score; it cannot satisfy this term without a frozen calibration
profile.

This calibration gate does not govern every output. An exact unambiguous
`explicitPolicy` follows its deterministic admission and conflict rules;
`genericAdvisor` may answer without personal evidence but must remain labeled
non-personal; and `abstention` is always available with a machine-readable
reason. Neither an explicit policy nor generic advice may be relabeled as an
inferred personal judgment.

For evaluation, $g$ denotes the frozen selection function for the declared
arm and basis; the runtime personal-inference instance is $g_{\mathrm{persona}}$.
Coverage and selective risk are

$$
\mathrm{Coverage}(g)=\mathbb{E}[g(q)]
$$

and

$$
R_{\mathrm{sel}}(f,g)=
\frac{\mathbb{E}[\ell(f(q),y)g(q)]}
{\mathbb{E}[g(q)]},
$$

when coverage is non-zero. Reporting accuracy without coverage would reward a
system that answers only trivial cases; reporting coverage without selective
risk would reward reckless guessing.

## 8. Cold start

At cold start, $\mathcal{E}_{\mathrm{persona}}(q)=\varnothing$. Therefore
$g_{\mathrm{persona}}(q;\Pi_v)=0$ and Mirror lacks personal evidence. An
applicable explicit policy remains a separate deterministic basis; Advisor may
still provide a generic proposal, marked non-personal:

$$
\mathrm{PersonaConfidence}_{0}=0,
\qquad
\mathrm{AdvisorCapability}_{0}\ge 0.
$$

Generic capability and evidence of personal fit are independent axes.

## 9. Mirror, Advisor, and authority

Mirror may compute the internal, non-authoritative candidate using a frozen,
label-blind total order $\mathrm{Tie}_v$ for probability ties:

$$
f_v(q)=\mathrm{Tie}_v\!\left(
\arg\max_{y}P_v(y\mid q,\mathcal{E}_{\mathrm{persona}}(q))\right),
\qquad
c_{\mathrm{internal}}(q)=\mathrm{MirrorCandidate}(f_v(q)).
$$

Only the deterministic basis resolver may construct `PublicJudgment`, using
Section 7 and the output order in Decision Semantics. The internal candidate is
never itself a public answer, policy input, adoption, or authority signal.

Advisor instead searches for a useful proposal $a$ under known constraints:

$$
a^*_{\mathrm{advisor}}
=\arg\max_a\mathbb{E}[U(a,o)\mid q,\mathcal{E}(q)],
$$

but must not present $a^*$ as what the user would have chosen.

Prediction is not permission. For the uniquely selected canonical
$\gamma_{\mathrm{auth}}$, an action may execute only when

$$
\mathrm{Execute}(a;\gamma_{\mathrm{auth}})=
I_{\mathrm{requestBound}}(a,\gamma_{\mathrm{auth}})
I_{\mathrm{capability}}(\gamma_{\mathrm{auth}})
I_{\mathrm{explicitGrant}}(\gamma_{\mathrm{auth}})
I_{\mathrm{scope}}(\gamma_{\mathrm{auth}})
I_{\mathrm{confirmation}}(\gamma_{\mathrm{auth}})
I_{\mathrm{audit}}(\gamma_{\mathrm{auth}})
I_{\mathrm{killSafe}}(\gamma_{\mathrm{auth}}).
$$

No persona score appears in this equation. In the current V1,
$I_{\mathrm{capability}}=0$ for sending or autonomous execution.

Judgment/adoption continue in [Decision Semantics](decision-semantics.md), and
tuple selection in [Privacy Invariants](privacy-and-falsification.md#p5--authority-independence).
Learning, deletion, and evaluation continue in [Learning, Privacy, and Evaluation](learning-privacy-evaluation.md).
