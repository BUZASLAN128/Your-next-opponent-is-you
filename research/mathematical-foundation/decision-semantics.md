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
I[\mathrm{subjectId}(c)=u_q]\,
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

The public output is a disjoint tagged union:

$$
\mathrm{PublicJudgment}[T]=
\mathrm{ExplicitPolicy}[T]\mid
\mathrm{InferredPersona}[T]\mid
\mathrm{GenericAdvisor}[T]\mid
\mathrm{Abstention}[\mathrm{Reason}].
$$

`MirrorCandidate[T]` is an internal type and is not a member of
`PublicJudgment[T]`. Only the deterministic basis resolver may construct a
public variant; serialization, logging, or fallback code cannot unwrap an
internal candidate directly.

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

Conflict is assessed only inside a full reviewed key

$$
K(c)=(\mathrm{subjectId}(c),\mathrm{targetLayer}(c),
\mathrm{reviewedDecisionKey}(c)).
$$

The final component identifies one decision question; a model may propose it,
but only a review receipt can establish the full key for canonical use.

Let $\mathrm{ValidSupersedes}_q$ be the query-relative relation defined in
Section 4. The active decision group is

$$
G_k(q)=\{c\in\mathcal{E}(q):
K(c)=k\land
\nexists c'\in\mathcal{E}(q):
\mathrm{ValidSupersedes}_q(c',c)\}.
$$

Every canonical claim has exactly one reviewed key whose record also binds its
target layer. Missing, malformed, model-only, or receipt-unbound keys fail
admission and cannot enter persona evidence. For every two distinct members of
one group, $C$ is symmetric and total; a missing assessment is `unknown`.

Conflict is unsafe only for a distinct pair:

$$
\mathrm{UnsafeConflict}(G_k)=
I[\exists c_i,c_j\in G_k:c_i\ne c_j\land
C(c_i,c_j)\ne\mathrm{compatible}].
$$

Let $\mathrm{SupersessionInvalid}(k,q)=1$ when a stored edge relevant to full
key $k$ has a missing endpoint, broken receipt/head/tuple binding, cross-key
endpoint, or cycle. The complete group gate is

$$
\mathrm{UnsafeDecisionGroup}(k,q)=
I[\mathrm{SupersessionInvalid}(k,q)=1\lor
\mathrm{UnsafeConflict}(G_k(q))=1].
$$

Mirror must abstain for that decision key when `incompatible` or `unknown`
appears and no explicit supersession resolves it. Different decision keys do
not conflict merely because their labels differ. Recency, frequency,
similarity, or model confidence cannot resolve a conflict.

### 3.1 Required decision-group closure

Conflict safety cannot depend on a model choosing which keys to inspect. For a
versioned output contract $v$, define

$$
\mathcal{K}_{\mathrm{req}}(q,v)=
\mathrm{Closure}_{\mathrm{dep}}
(\mathrm{Manifest}_v(m_q,\mathrm{requestedOutput}(q)))
$$

and

$$
\mathcal{G}_{\mathrm{req}}(q,v)=
\{G_k(q):k\in\mathcal{K}_{\mathrm{req}}(q,v)\}.
$$

The manifest is a deterministic, versioned system-control input selected
before candidate generation. It includes the transitive decision-key
dependencies of every rule, predicate, basis selector, content field, and
rationale field that may affect the requested output. A model, extractor,
candidate answer, or ranking score cannot author or narrow it.

If the manifest is missing, its version is stale, a dependency cannot be
resolved, or resolution reads or is influenced by an applicable key outside
the declared closure, Mirror fails closed. This makes omission of a conflicting
key an abstention condition rather than a way to manufacture an empty conflict
set.

## 4. Supersession

Let $c_i\succ c_j$ mean a verified review event explicitly names $c_i$ as a
successor to $c_j$. The stored relation is acyclic:

$$
c_i\succ^{+}c_i\quad\mathrm{is\ forbidden}.
$$

One stored edge changes the active projection for query $q$ only when

$$
\mathrm{ValidSupersedes}_q(c_i,c_j)=
I[c_i\ne c_j]I[c_i\succ c_j]I[\mathrm{Applies}(c_i,q)]
I[K(c_i)=K(c_j)].
$$

An expired, future, revoked, inadmissible, wrong-subject, wrong-key, or
wrong-layer successor cannot hide an otherwise active claim. A narrower
successor supersedes only where its own scope applies. Supersession preserves
the historical source, adoption, and earlier receipt. Its review receipt binds
both claim IDs and immutable tuple hashes, the review, and expected head.
Missing endpoints, a broken binding, or a cycle sets
`SupersessionInvalid(k,q)` and forces abstention; it is never repaired by
recency.

## 5. Verified adoption boundary

The V1.7 target trust model trusts the authenticated operating-system user and
a separate approval channel. The model, extractor, reasoner, application
runtime, and ordinary projection code must not be able to write a verified
adoption. The current base does not yet implement that independent channel.

A candidate adoption record is

$$
r_{\mathrm{adopt}}=(\mathrm{subjectId},\mathrm{reviewId},\mathrm{claimId},
\mathrm{claimTupleHash},\mathrm{fullDecisionKey},\mathrm{expectedHead},
\mathrm{channelId},\mathrm{challenge},\mathrm{response},
\mathrm{receiptHash}).
$$

Verification must bind subject, review, immutable claim tuple, full decision
key, current head, approval channel, fresh challenge, and response. A receipt
replayed or rebound for another field fails closed. Challenge reuse also fails
closed.

A hash proves that bytes have not changed since hashing. It does not prove
human presence, user intent, device integrity, or channel independence.
Administrator or root compromise is an explicit V1 out-of-scope threat, not a
solved property. The concrete authenticator remains an open decision.

## 6. Output rule

For each decision key, the resolver follows this order:

1. reject inadmissible or inapplicable claims;
2. apply only query-valid explicit supersession;
3. assess the remaining same-key relations;
4. abstain on `incompatible` or `unknown`;
5. use an exact explicit policy when one unambiguous policy remains;
6. use inferred persona only with a valid calibration profile;
7. otherwise Mirror abstains; Advisor may independently return labeled generic
   advice without unwrapping a Mirror candidate.

No step grants send, execute, promote, or impersonation authority.
