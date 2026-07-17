# Formal System Model

> Status: technology-neutral candidate model with hard safety invariants

## 1. State and notation

Let the represented person be $u$, the evaluation time be $t$, and a request be

$$
q=(x,s,t,m),
$$

where $x$ is task context, $s$ is the requested scope, and $m$ is the operating
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
\operatorname{Admit}(c)=
I_{\mathrm{user}}
I_{\mathrm{holder}}
I_{\mathrm{adopted}}
I_{\mathrm{source}}
I_{\mathrm{receipt}}
I_{\mathrm{class}}
I_{\mathrm{status}}.
$$

The indicators mean:

- $I_{\mathrm{user}}$: the adoption actor is the user;
- $I_{\mathrm{holder}}$: the claim holder is the represented user;
- $I_{\mathrm{adopted}}$: one explicit correction/adoption action exists;
- $I_{\mathrm{source}}$: literal spans still match immutable source evidence;
- $I_{\mathrm{receipt}}$: the complete review and receipt chain verifies;
- $I_{\mathrm{class}}$: data-class transitions are allowed;
- $I_{\mathrm{status}}$: the claim is confirmed and neither invalidated nor
  superseded.

Because this is a product invariant rather than a learned probability,
`Admit(c)` is Boolean and fail-closed. Repetition, embedding similarity, model
confidence, or recency cannot replace a missing factor.

## 3. Applicability at query time

For a query $q$, a canonical claim is applicable only when

$$
\operatorname{Use}(c,q)=
\operatorname{Admit}(c)
\cdot I[s_c\preceq s_q]
\cdot I[b_c\le t_q\le e_c]
\cdot I[u_c=u_q]
\cdot I[\neg\operatorname{revoked}(c)].
$$

Here $s_c\preceq s_q$ means that the stored scope is compatible with, and not
broader than, the requested person, project, role, audience, risk, and time.
Missing bounds are explicit unbounded values, not inferred defaults.

The eligible set is

$$
\mathcal{E}(q)=\{c\in C_t:\operatorname{Use}(c,q)=1\}.
$$

## 4. Supersession and conflict

Let $c_i\succ c_j$ mean an explicit reviewed event supersedes $c_j$ with
$c_i$. Supersession must be acyclic:

$$
c_i\succ^{+}c_i\quad\text{is forbidden}.
$$

Let $c_i\perp c_j$ mean two simultaneously applicable claims prescribe
incompatible judgments in the same target layer. The unresolved conflict set is

$$
\mathcal{K}(q)=
\{(c_i,c_j)\in\mathcal{E}(q)^2:c_i\perp c_j\land
\neg(c_i\succ c_j)\land\neg(c_j\succ c_i)\}.
$$

If $\mathcal{K}(q)\ne\varnothing$, Mirror must abstain. Neither newest-wins,
majority vote, nor highest embedding score may silently choose a side.

## 5. Relevance without false authority

Eligible claims may be ordered by a candidate feature vector

$$
\rho(c,q)=
(\operatorname{semantic}(c,q),
\operatorname{scopeSpecificity}(c,q),
\operatorname{temporalFit}(c,q),
\operatorname{outcomeSupport}(c),
\operatorname{evidenceQuality}(c)).
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
I[\operatorname{provenanceComplete}]
I[\operatorname{scopeSafe}]
I[\operatorname{calibratedConfidence}\ge\theta].
$$

$\theta$ is not selected yet. It must be calibrated before a real sealed run.

Coverage and selective risk are

$$
\operatorname{Coverage}(g)=\mathbb{E}[g(q)]
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
\operatorname{PersonaConfidence}_{0}=0,
\qquad
\operatorname{AdvisorCapability}_{0}\ge 0.
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
\operatorname{Execute}(a)=
I_{\mathrm{capability}}
I_{\mathrm{explicitGrant}}
I_{\mathrm{scope}}
I_{\mathrm{confirmation}}
I_{\mathrm{audit}}
I_{\mathrm{killSafe}}.
$$

No persona score appears in this equation. In the current V1,
$I_{\mathrm{capability}}=0$ for sending or autonomous execution.

Learning, deletion, privacy, and evaluation equations continue in
[Learning, Privacy, and Evaluation](learning-privacy-evaluation.md).
