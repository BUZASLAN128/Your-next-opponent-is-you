# Decision Semantics

> Status: V1 research contract with hard invariants and unselected parameters

This document defines when represented-user evidence applies and what kind of
answer it may support. It deliberately separates deterministic policy,
inferred persona, generic advice, and abstention.

> **Implementation gap:** This is the required target contract, not current
> runtime behavior. At the reviewed base, risk `unknown` still behaves as a
> wildcard and `any` is not represented; canonical claims have no reviewed
> `decision_key`; and an ordinary correction receipt can satisfy adoption
> without an independent authenticator, fresh challenge, or expected-head
> proof. Mirror must not claim these V1.7 guarantees until the handoff's red
> tests pass in a separately authorized implementation.

## 1. Query and scope

Let a query be

$$
q=(x,\omega_q,t_q,u_q,m_q),
$$

where $x$ is task context, $\omega_q$ is the concrete query environment,
$t_q$ is evaluation time, $u_q$ is the represented subject, and $m_q$ is the
operating mode. A stored scope $s_c$ is a predicate over environments, not a
position in a total ordering.

Applicability is

$$
\mathrm{Applies}(c,q)=
\mathrm{Admit}(c)\,
I[\omega_q\models s_c]\,
I[t_q\in[b_c,e_c]]\,
I[u_c=u_q]\,
I[\neg\mathrm{revoked}(c)].
$$

The environment includes person, project, repository or path, role, audience,
risk, and other declared dimensions. Every matcher is explicit:

- a missing project, role, or audience constraint is general and therefore
  matches a more specific query;
- a specific stored value matches only that value and never expands to a
  general or different query;
- `any` is the only wildcard risk value;
- `unknown` matches only `unknown`;
- a canonical scope with a missing risk value is invalid rather than an
  implicit wildcard;
- known risk values match exactly unless a separately reviewed policy defines
  a set-valued predicate;
- unknown risk never inherits a high-risk rule by implication.

An absent field and an observed-but-unknown field therefore have different
semantics. Normalization must preserve that distinction.

The eligible set is

$$
\mathcal{E}(q)=\{c:\mathrm{Applies}(c,q)=1\}.
$$

## 2. Judgment basis

Every output has exactly one basis:

$$
\mathrm{Basis}\in
\{\mathrm{explicitPolicy},\mathrm{inferredPersona},
\mathrm{genericAdvisor},\mathrm{abstention}\}.
$$

The bases have different admission rules:

| Basis | Permitted source | Required behavior |
| --- | --- | --- |
| `explicitPolicy` | Exact, applicable, user-adopted project or control rule | Apply deterministically when unambiguous |
| `inferredPersona` | Applicable persona evidence plus a frozen calibration profile | Label as a personal inference; expose uncertainty |
| `genericAdvisor` | Generic reasoning under public or explicitly permitted context | Never describe it as the user's likely choice |
| `abstention` | Missing, conflicting, unknown, unsafe, or uncalibrated basis | State the blocking reason |

A model-provided confidence number is not a calibration profile. Without
calibration, persona evidence may rank candidates but cannot justify the
`inferredPersona` basis.

## 3. Three-valued conflict

For two applicable claims,

$$
C(c_i,c_j)\in
\{\mathrm{compatible},\mathrm{incompatible},\mathrm{unknown}\}.
$$

Conflict is assessed only when both claims share the same user-reviewed
`decision_key`. The key identifies one decision question under the relevant
target layer; a model may propose it, but only a review receipt can establish
it for canonical use.

For a decision group $G_k(q)$:

$$
\mathrm{UnsafeConflict}(G_k)=
I[\exists c_i,c_j\in G_k:
C(c_i,c_j)\ne\mathrm{compatible}].
$$

Mirror must abstain for that decision key when `incompatible` or `unknown`
appears and no explicit supersession resolves it. Different decision keys do
not conflict merely because their labels differ. Recency, frequency,
similarity, or model confidence cannot resolve a conflict.

## 4. Supersession

Let $c_i\succ c_j$ mean a verified review event explicitly supersedes $c_j$
with $c_i$. The relation is acyclic:

$$
c_i\succ^{+}c_i\quad\mathrm{is\ forbidden}.
$$

Supersession preserves the historical record. It changes the active
projection; it does not rewrite the source, adoption, or earlier receipt.

## 5. Verified adoption boundary

The V1.7 target trust model trusts the authenticated operating-system user and
a separate approval channel. The model, extractor, reasoner, application
runtime, and ordinary projection code must not be able to write a verified
adoption. The current base does not yet implement that independent channel.

A candidate adoption record is

$$
a=(\mathrm{subjectId},\mathrm{reviewId},\mathrm{claimId},
\mathrm{expectedHead},\mathrm{channelId},\mathrm{challenge},
\mathrm{response},\mathrm{receiptHash}).
$$

Verification must bind subject, review, claim, current head, approval channel,
fresh challenge, and response. A receipt replayed for another subject, review,
claim, or head fails closed. Challenge reuse also fails closed.

A hash proves that bytes have not changed since hashing. It does not prove
human presence, user intent, device integrity, or channel independence.
Administrator or root compromise is an explicit V1 out-of-scope threat, not a
solved property. The concrete authenticator remains an open decision.

## 6. Output rule

For each decision key, the resolver follows this order:

1. reject inadmissible or inapplicable claims;
2. apply explicit supersession;
3. assess the remaining same-key relations;
4. abstain on `incompatible` or `unknown`;
5. use an exact explicit policy when one unambiguous policy remains;
6. use inferred persona only with a valid calibration profile;
7. otherwise return generic advice or abstention, preserving the basis label.

No step grants send, execute, promote, or impersonation authority.
