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
c_j=(\ell_j,\iota_j,k_j,s_j,[b_j,e_j],v_j,p_j),
$$

where $\ell_j$ is literal evidence, $\iota_j$ is interpretation, $k_j$ is the
target layer, $s_j$ is scope, $[b_j,e_j]$ is validity, $v_j$ is lifecycle
status, and $p_j$ is provenance.

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
I_{\mathrm{user}}
I_{\mathrm{holder}}
I_{\mathrm{adopted}}
I_{\mathrm{source}}
I_{\mathrm{receipt}}
I_{\mathrm{class}}
I_{\mathrm{status}}.
$$

The indicators mean:

- $I_{\mathrm{user}}$: the adoption actor is the authenticated operating-
  system user in the V1 trust model;
- $I_{\mathrm{holder}}$: the claim holder is the represented user;
- $I_{\mathrm{adopted}}$: one fresh, subject/review/claim/head-bound approval
  verifies through the separate adoption channel;
- $I_{\mathrm{source}}$: literal spans still match immutable source evidence;
- $I_{\mathrm{receipt}}$: the complete review and receipt chain verifies;
- $I_{\mathrm{class}}$: data-class transitions are allowed;
- $I_{\mathrm{status}}$: the claim is confirmed and neither invalidated nor
  superseded.

Because this is a product invariant rather than a learned probability,
`Admit(c)` is Boolean and fail-closed. Repetition, embedding similarity, model
confidence, or recency cannot replace a missing factor. The independent
adoption mechanism is a V1.7 target and is not implemented in the reviewed
base. Its trust boundary and hash limitation are defined in
[Decision Semantics](decision-semantics.md#5-verified-adoption-boundary).

## 3. Applicability at query time

Scope is a predicate over the concrete query environment, not a total or
partial ordering between stored and requested scopes:

$$
\mathrm{Applies}(c,q)=
\mathrm{Admit}(c)\,
I[\omega_q\models s_c]\,
I[t_q\in[b_c,e_c]]\,
I[u_c=u_q]\,
I[\neg\mathrm{revoked}(c)].
$$

The exact matching semantics, including the distinction between `any`,
`unknown`, and an absent constraint, are normative in
[Decision Semantics](decision-semantics.md#1-query-and-scope).

## 4. Supersession and conflict

Let $c_i\succ c_j$ mean an explicit reviewed event supersedes $c_j$ with
$c_i$. Supersession must be acyclic:

$$
c_i\succ^{+}c_i\quad\mathrm{is\ forbidden}.
$$

Conflict is three-valued and assessed only inside a user-reviewed
`decision_key`:

$$
C(c_i,c_j)\in
\{\mathrm{compatible},\mathrm{incompatible},\mathrm{unknown}\}.
$$

For the same key, both `incompatible` and `unknown` force Mirror to abstain
unless explicit supersession resolves the pair. Different keys do not conflict
merely because their labels differ. Neither newest-wins, majority vote, nor
highest embedding score may silently choose a side. See
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

## 7. Abstention and selective risk

Let $f(q)$ be a predicted decision and $g(q)\in\{0,1\}$ be the selection
function. The system answers only when $g(q)=1$:

$$
\hat y(q)=
\begin{cases}
f(q), & g(q)=1,\\
\bot, & g(q)=0.
\end{cases}
$$

The hard selection gate is

$$
g(q)=I[\mathcal{E}(q)\ne\varnothing]
I[\mathcal{K}(q)=\varnothing]
I[\mathrm{provenanceComplete}]
I[\mathrm{scopeSafe}]
I[\mathrm{calibratedProbability}\ge\tau].
$$

$\tau$ is not selected yet. A model-provided confidence is only a ranking
score; it cannot satisfy this term without a frozen calibration profile.

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

At cold start, $\mathcal{E}(q)=\varnothing$. Therefore Mirror has
$g(q)=0$ and must say it lacks personal evidence. Advisor may still provide a
generic proposal from the replaceable reasoner, but its output is marked as
non-personal:

$$
\mathrm{PersonaConfidence}_{0}=0,
\qquad
\mathrm{AdvisorCapability}_{0}\ge 0.
$$

Generic capability and evidence of personal fit are independent axes.

## 9. Mirror, Advisor, and authority

Mirror estimates

$$
\hat y_{\mathrm{mirror}}
=\arg\max_{y}P(y\mid q,\mathcal{E}(q)).
$$

Advisor instead searches for a useful proposal $a$ under known constraints:

$$
a^*_{\mathrm{advisor}}
=\arg\max_a\mathbb{E}[U(a,o)\mid q,\mathcal{E}(q)],
$$

but must not present $a^*$ as what the user would have chosen.

Prediction is not permission. An action may execute only when

$$
\mathrm{Execute}(a)=
I_{\mathrm{capability}}
I_{\mathrm{explicitGrant}}
I_{\mathrm{scope}}
I_{\mathrm{confirmation}}
I_{\mathrm{audit}}
I_{\mathrm{killSafe}}.
$$

No persona score appears in this equation. In the current V1,
$I_{\mathrm{capability}}=0$ for sending or autonomous execution.

Judgment bases and adoption continue in [Decision Semantics](decision-semantics.md).
Learning, deletion, privacy, and evaluation equations continue in
[Learning, Privacy, and Evaluation](learning-privacy-evaluation.md).
