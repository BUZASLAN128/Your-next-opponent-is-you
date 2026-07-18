# State, Privacy, and Erasure

> Status: V1 hard-invariant research contract; runtime mechanisms unselected

> **Implementation gap:** The reviewed base does not yet provide the complete
> expected-head append, observer-indexed trace, producer registry, post-delete
> independence proof, or tombstone fence defined here. Existing receipts,
> egress blocking, and dependency deletion are partial apparatus only.

## 1. Linearizable review append

The learning stream is append-only. Its trusted append context is

$$
\gamma_e=(\mathrm{actorId},\mathrm{subjectId},\mathrm{reviewId},
\mathrm{adoptionRef},\mathrm{appendAuthReceipt},\mathrm{policyVersion}),
$$

and a proposed event is

$$
e=(\mathrm{eventId},\mathrm{streamId},\mathrm{expectedRevision},
\mathrm{type},\mathrm{payloadHash},\mathrm{causationId},\gamma_e).
$$

The outer call context must equal the event's canonical context before any
authorization or storage decision. Let $v_e=\gamma.\mathrm{policyVersion}$ be
the event-bound version and $v_{\mathrm{cur}}$ the current policy version for a
new event:

$$
\begin{aligned}
\mathrm{AppendAuthorized}^{\mathrm{new}}_{v_{\mathrm{cur}}}(e,\gamma)=
&I[e.\gamma_e=\gamma]
I[v_e=v_{\mathrm{cur}}]
I[\mathrm{trustedActor}_{v_{\mathrm{cur}}}(\gamma)]
I[\mathrm{contextBound}_{v_{\mathrm{cur}}}(e,\gamma)]\\
&I[\mathrm{eventTypeAllowed}_{v_{\mathrm{cur}}}(e.\mathrm{type},\gamma)]
I[\mathrm{adoptionSatisfied}_{v_{\mathrm{cur}}}(e.\mathrm{type},\gamma)].
\end{aligned}
$$

An existing exact retry instead uses

$$
\mathrm{RetryAuthorized}_{v_e}(e,\gamma)=
I[e.\gamma_e=\gamma]I[\mathrm{sameActorAuthenticated}(\gamma)]
I[\mathrm{VerifyAppendAuthReceipt}_{v_e}(e,\gamma)].
$$

The context and its immutable append-authorization receipt bind actor, subject,
review, stream, event type, policy version, and any required adoption. An
`adoptionRef=none` is valid only for event types that cannot affect admission or
supersession. Models and ordinary runtime code cannot manufacture this context
or choose a less restrictive type.

`ReviewAppend(e,\gamma)` canonicalizes and checks context equality, then makes
a non-disclosing `eventId` lookup. For an existing ID, a changed tuple rejects;
an identical tuple creates no second effect and returns the original
non-content-bearing acknowledgement only when the same actor authenticates and
the original bound authorization receipt verifies under its recorded policy
version. Otherwise it denies without revealing whether the ID exists. Current
policy is evaluated only for a new event; later policy or adoption change cannot
reapply an old event. A new event must satisfy `AppendAuthorized` at
$v_{\mathrm{cur}}$; an existing exact retry uses `RetryAuthorized` at its
recorded $v_e$ and never appends. Only a new event compares its expected
revision with the current stream head.

Its observable outcomes are:

- a new `eventId` at the expected head appends once;
- the same `eventId` with the identical canonical event tuple is an idempotent
  retry: it never appends again, and returns the original acknowledgement only
  under the retry rule above;
- the same `eventId` with any different bound field, including payload hash,
  stream, type, causation, actor, subject, review, or adoption context, is
  rejected;
- a stale or future expected revision is rejected fail-closed;
- of two concurrent appends against one head, at most one succeeds.

Each successful append is linearized at one indivisible head transition.
Projection is a deterministic fold over the accepted sequence:

$$
M_n=\mathrm{fold}(U,M_0,[e_1,\ldots,e_n]).
$$

This is a behavioral contract, not a database or transaction-isolation
selection. Append authority is not adoption authority: admission still
requires the independently verified adoption contract.

## 2. Observer-indexed noninterference

Let $\ell$ be public or explicitly declassified state, $h$ be private D1-D5
state and all its derivatives, $P$ be a program, and $o$ be an external
observer. Privacy requires:

$$
\pi_o(\mathrm{Trace}(P,\ell,h_1))
=
\pi_o(\mathrm{Trace}(P,\ell,h_2)).
$$

The projection $\pi_o$ includes every externally observable logical event:

- destination, provider, endpoint class, and selected model;
- canonical payload digest and byte size;
- permitted header-name and header-value classes;
- call count, order, retry count, and termination state;
- error class and fallback path;
- externally visible log and telemetry egress.

Testing request bodies alone is insufficient. If timing, scheduling, or
resource contention is placed in the threat model, deterministic trace
equality must be replaced by an explicitly selected observational or
distributional equivalence. That stronger timing model remains open.

For V1 external adapters, the declassification set for D1-D5 identity data is
empty. Adding or changing private state must not change the external logical
trace. Loopback transport alone is not locality proof.

## 3. Erasure registry

Let $a\rightarrow b$ mean that artifact $b$ derives from $a$. The dependency
closure of source $s$ is

$$
D^+(s)=\{s\}\cup\{v:\exists\mathrm{\ path\ }s\rightarrow^+v\}.
$$

For a source set $S$, closure is pointwise union:

$$
D^+(S)=\bigcup_{s\in S}D^+(s).
$$

For contract version $v$, let $\mathcal{U}_v$ be the complete declared
in-boundary universe of private persistence and artifact producers and
$\mathcal{R}_v$ the producers registered with a version-bound erasure handler
and parity test. Let $\alpha_v$ be an independently verified
universe attestation binding the declared product boundary, inventory and
registry digests, discovery/check version, relevant product/configuration/
artifact versions, scope, and time. Registry completeness is

$$
\begin{aligned}
\mathrm{RegistryComplete}(v)=
&I[\mathrm{VerifyUniverseAttestation}(\alpha_v)]
I[\mathcal{U}_v=\mathcal{R}_v]\\
&I[\forall p\in\mathcal{U}_v:
\mathrm{handlerBound}(p,v)\land\mathrm{parityPass}(p,v)].
\end{aligned}
$$

Any bound product, configuration, artifact, inventory, or registry change
makes $\alpha_v$ stale. Self-registration alone is insufficient. Attestation
is evidence only within its declared boundary; it cannot prove that an
undiscovered or out-of-boundary producer does not exist. Its concrete
mechanism remains unselected.

An erasure receipt

$$
r_{\mathrm{erase}}=(\mathrm{sourceId},\mathrm{closureDigest},v,
\mathrm{handlerOutcomes},\mathrm{recoveryScope},\mathrm{backupScope},
\mathrm{tombstoneId})
$$

is non-content-bearing and binds the verified closure, current universe,
handler outcomes, declared recovery/backup boundary, and tombstone.

Deletion success requires all five conditions:

$$
\mathrm{DeleteSuccess}(s;v)=
I[\mathrm{closureAbsent}(D^+(s))]
I[\mathrm{RegistryComplete}(v)]
I[\mathrm{VerifyErasureReceipt}(r_{\mathrm{erase}},s,v)]
I[\mathrm{PostDeleteIndependent}_v(s)]
I[\mathrm{tombstoneFence}_v(s)].
$$

`closureAbsent` covers active rows, files, indexes, embeddings, caches,
reports, projections, backups governed by the product, and other registered
derivatives. For deletion time $t_d$, let $h_1\equiv_{\neg D^+(s)}h_2$ mean two
pre-delete states differ only in the source closure, and let
$\mathcal{F}_{s,v}$ contain every admissible future request, retry, delayed
worker, import, restore, and recovery schedule. Then

$$
\begin{aligned}
\mathrm{PostDeleteIndependent}_v(s)=1\iff
\forall h_1,h_2\ \forall\eta\in\mathcal{F}_{s,v}\ \forall T\ge t_d:\quad
&h_1\equiv_{\neg D^+(s)}h_2\Rightarrow\\
&\pi_{\mathrm{product}}(\mathrm{Trace}_{[t_d,T]}
(P,\mathrm{Erase}_s(h_1),\eta))\\
&=\pi_{\mathrm{product}}(\mathrm{Trace}_{[t_d,T]}
(P,\mathrm{Erase}_s(h_2),\eta)).
\end{aligned}
$$

The product projection includes returned judgments, retrieval, persistence and
derivation events, model inputs, logs, telemetry, and external calls. The
tombstone fence rejects any replay, retry, delayed worker, import, restore, or
recovery that tries to recreate the source or a descendant.

A non-content-bearing tombstone may retain identifiers necessary to enforce
the fence, subject to a later retention decision. It must not preserve the
deleted content or a reversible content-derived value.

## 4. Parametric-memory prohibition

Let $\mathcal{H}$ be every D1-D5 private item and let
$\mathcal{H}^{+}=\bigcup_{x\in\mathcal{H}}D^+(x)$ include all transformed
derivatives. Let $\mathrm{UpdateInfluence}$ contain examples, labels, rewards,
gradients, summaries, selectors, hyperparameters, adapters, steering artifacts,
and every other value capable of changing model parameters or choosing a
parameter artifact. V1 requires

$$
\mathcal{H}^{+}\cap\mathrm{UpdateInfluence}=\varnothing
$$

and, for equal public update state $\ell$,

$$
\forall h_1,h_2:\quad
\mathrm{Update}(\theta,\ell,h_1)=
\mathrm{Update}(\theta,\ell,h_2)=
\mathrm{Update}(\theta,\ell).
$$

D1-D3 data would require a separately approved purpose, consent and authority
model, retention rule, and validated unlearning and erasure proof before a
future exception could even be evaluated. Credentials and third-party personal
data do not gain a training path from such an exception. Direct input and
indirect influence through labels, rewards, summaries, selection, or tuning are
equally forbidden in V1. External structured memory can be deleted and fenced;
model weights cannot be claimed erased merely because the source row was
removed.

## 5. Proof obligations

Erasure evidence must show a current bound universe attestation, registry
parity, closure traversal, physical or cryptographic removal under the selected
storage contract, the quantified future-trace comparison, verified erasure
receipt, and tombstone enforcement. A content hash, self-declared registry, or
source-row deletion alone proves none of these properties.
