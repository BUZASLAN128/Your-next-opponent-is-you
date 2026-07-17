# State, Privacy, and Erasure

> Status: V1 hard-invariant research contract; runtime mechanisms unselected

> **Implementation gap:** The reviewed base does not yet provide the complete
> expected-head append, observer-indexed trace, producer registry, post-delete
> independence proof, or tombstone fence defined here. Existing receipts,
> egress blocking, and dependency deletion are partial apparatus only.

## 1. Linearizable review append

The learning stream is append-only. A proposed event is

$$
e=(\mathrm{eventId},\mathrm{streamId},\mathrm{expectedRevision},
\mathrm{type},\mathrm{payloadHash},\mathrm{causationId}).
$$

`ReviewAppend(e)` first checks whether `eventId` already exists, then validates
the expected revision against the stream head for a new event. Its observable
outcomes are:

- a new `eventId` at the expected head appends once;
- the same `eventId` with the identical canonical event tuple is an idempotent
  retry and returns the original result;
- the same `eventId` with any different bound field, including payload hash,
  stream, type, or causation, is rejected;
- a stale or future expected revision is rejected fail-closed;
- of two concurrent appends against one head, at most one succeeds.

Each successful append is linearized at one indivisible head transition.
Projection is a deterministic fold over the accepted sequence:

$$
M_n=\mathrm{fold}(U,M_0,[e_1,\ldots,e_n]).
$$

This is a behavioral contract, not a database or transaction-isolation
selection.

## 2. Observer-indexed noninterference

Let $\ell$ be public or explicitly declassified state, $h$ be private D1-D5
state, $P$ be a program, and $o$ be an external observer. Privacy requires:

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

Let $\mathcal{P}$ be all private persistence and artifact producers and
$\mathcal{R}$ the registered producers with an erasure handler and parity
test. Registry completeness is

$$
\mathcal{P}\subseteq\mathcal{R}.
$$

Deletion success requires all four conditions:

$$
\mathrm{DeleteSuccess}(s)=
I[\mathrm{closureAbsent}(D^+(s))]
I[\mathcal{P}\subseteq\mathcal{R}]
I[\mathrm{postDeleteIndependent}(s)]
I[\mathrm{tombstoneFence}(s)].
$$

`closureAbsent` covers active rows, files, indexes, embeddings, caches,
reports, projections, backups governed by the product, and other registered
derivatives. `postDeleteIndependent` means future outputs are unchanged by the
deleted content. `tombstoneFence` rejects any later replay, retry, delayed
worker, or import that tries to recreate the source or a descendant.

A non-content-bearing tombstone may retain identifiers necessary to enforce
the fence, subject to a later retention decision. It must not preserve the
deleted content or a reversible content-derived value.

## 4. Parametric-memory prohibition

Until a separately specified and validated unlearning mechanism exists:

$$
\forall x:\mathrm{class}(x)\in\{D2,D3\}
\Rightarrow x\notin\mathrm{TrainingInput}.
$$

D2-D3 derived identity data cannot enter fine-tuning, adapter weights,
activation steering artifacts, or any other parameter update. External memory
can be deleted and fenced; model weights cannot be claimed erased merely
because the source row was removed.

## 5. Proof obligations

Erasure evidence must show registry completeness, closure traversal, physical
or cryptographic removal according to the selected storage contract,
post-delete behavioral independence, and tombstone enforcement across retry
and recovery. A content hash or a source-row deletion alone proves none of
these properties.
