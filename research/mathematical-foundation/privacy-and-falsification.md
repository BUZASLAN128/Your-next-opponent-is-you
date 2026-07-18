# Privacy Invariants and Falsification Matrix

> Date: 2026-07-17
> Evidence tier: repository source and history scan; no private corpus read

## Repository privacy scan

The scan covered tracked files and non-ignored untracked files visible in the
current worktree. Pattern classes included private keys, common provider-token
forms, credential assignments, actual user-profile paths, host names, private
IP addresses, email addresses, phone/identity-number shapes, Codex attachment
paths, and local-drive paths. Potential matches were reviewed by location
rather than bulk-printing matched values.

### Confirmed current-tree result

- No private key, common provider token, actual credential assignment, device
  name, actual user-profile path, private IPv4 address, MAC address, or SSH
  public key was found.
- Windows paths in public examples use explicit placeholders or synthetic test
  markers.
- Database credentials in tests and `.env.example` are documented local-only
  fixtures, not observed machine credentials.
- Model revision, byte count, and digest describe a public model artifact, not
  the computer or the user's private corpus.
- Public project and repository names are intentional project identity, not
  private host identity.

### Confirmed privacy defect corrected in the current tree

Several research records disclosed exact aggregate outcomes from a private
represented-user correction session and the exact size of its dependency
projection. These values contained no source text, but they were behavioral
and operational metadata derived from private identity work. The current
research tree now replaces them with categorical statements such as partial,
complete, replayed, or projection-only.

### Historical residual

Git history still contains earlier versions of those aggregate values and one
generic local workspace path. Current-tree redaction cannot remove reachable
historical blobs. Removing them from the public branch requires a separate,
explicit history-replacement decision, a verified remote SHA, a local rollback
reference, and `--force-with-lease`. This document does not authorize that
operation.

## Hard privacy invariants

### P1 — Public/private separation

Let $G$ be the set of Git-visible artifacts. Then

$$
\forall x\in G:\quad
\mathrm{class}(x)\in
\{D0,\mathrm{public\ source},\mathrm{redacted\ category}\}.
$$

Raw corpus, derived identity, private task content, credentials, third-party
personal data, exact private locators, and private artifact fingerprints must
not belong to $G$.

### P2 — No external private egress

Let $\mathcal{H}$ be all D1-D5 private state and
$\mathcal{H}^{+}=\bigcup_{x\in\mathcal{H}}D^+(x)$ include its transformed
derivatives. Then

$$
\forall x\in\mathcal{H}^{+}:\quad
\mathrm{externalSend}(x)=0.
$$

Loopback is a transport property, not proof of provider locality. Locality and
artifact identity need independent attestation.

### P3 — Provenance completeness

$$
\mathrm{Admit}(c)=1
\Rightarrow
\mathrm{retrievableIdentity}(c)\land
\mathrm{source}(c)\land\mathrm{adoption}(c)\land
\mathrm{receiptChain}(c)\land\mathrm{reviewedDecisionKey}(c).
$$

If any term is missing, the claim may be inspected as a quarantined proposal
but cannot support Mirror.

### P4 — Deletion completeness

$$
\mathrm{DeleteSuccess}(s;v)=
I[\mathrm{closureAbsent}(D^+(s))]
I[\mathrm{RegistryComplete}(v)]
I[\mathrm{VerifyErasureReceipt}(r_{\mathrm{erase}},s,v)]
I[\mathrm{PostDeleteIndependent}_v(s)]
I[\mathrm{tombstoneFence}_v(s)].
$$

This includes derived reports, embeddings, claims, continuity edges, indexes,
and private presentation artifacts. In V1, D1-D5 private data and its
derivatives cannot influence model parameters. A later exception requires a
separately approved
purpose, authority, retention, deletion, and unlearning contract; none is
implied here.

### P5 — Authority independence

Let $\ell_{\mathrm{auth}}$ be trusted identity, immutable resource, control,
grant, and explicitly confirmed action-request state. A model proposal is not
trusted request state. Let $h$ be all persona-, model-, extractor-, or
reasoner-derived state. The canonical authorization tuple is

$$
\gamma_{\mathrm{auth}}=(\mathrm{actorId},\mathrm{subjectId},
\mathrm{confirmedActionDigest},\mathrm{resourceId},\mathrm{capability},
\mathrm{grantId},\mathrm{scope},\mathrm{confirmationReceipt},
\mathrm{auditContext},\mathrm{killSafetyState},\mathrm{policyVersion}).
$$

Stable IDs and enum values are canonical; grant and confirmation receipts must
verify and bind the same actor, subject, action, resource, scope, and policy.
`TrustedMatch(\gamma_{\mathrm{auth}},\ell_{\mathrm{auth}})=1` means every bound
field matches. $\mathrm{SelectAuth}_{T}$ returns the unique trusted match or
$\bot$ on zero or multiple matches:

$$
\mathrm{SelectAuth}_{T}(\ell)=
\begin{cases}
\gamma, & \exists!\gamma:\mathrm{TrustedMatch}(\gamma,\ell)=1,\\
\bot, & \mathrm{otherwise}.
\end{cases}
$$

The selector must satisfy

$$
\forall\ell_{\mathrm{auth}},h_1,h_2:\quad
\mathrm{SelectAuth}(\ell_{\mathrm{auth}},h_1)=
\mathrm{SelectAuth}(\ell_{\mathrm{auth}},h_2)=
\mathrm{SelectAuth}_{T}(\ell_{\mathrm{auth}}).
$$

$$
\forall\ell_{\mathrm{auth}},\gamma,h:\quad
[\gamma=\mathrm{SelectAuth}_{T}(\ell_{\mathrm{auth}})\land\gamma\ne\bot]
\Rightarrow
\pi_{\mathrm{auth}}(\gamma,h)=\gamma
\quad\land\quad
\mathrm{Authorize}(\gamma,h)=\mathrm{Policy}(\gamma).
$$

This is selector and field noninterference, not a correlation. No value derived
from $h$ may choose a grant or populate or alter its request, scope,
confirmation, capability, audit, or kill-safety inputs. Request substitution
after confirmation fails the trusted binding.
Tests must exercise the pure policy oracle with capability synthetically
enabled so the invariant cannot pass only because V1 runtime capability is
fixed to zero. This synthetic oracle authorizes no product action. The
conjunctive execution gate in
[Formal System Model](formal-system.md#9-mirror-advisor-and-authority) remains
the necessary action contract.

## Falsification matrix

| Claim | Observation that would falsify it | Required evidence |
| --- | --- | --- |
| Public Git contains no private identity data | A tracked or reachable historical blob contains raw text, a private locator, private artifact fingerprint, or behaviorally identifying aggregate | Current-tree and history scan plus human review |
| Mirror uses only adopted represented-user evidence | A proposed, assistant-authored, third-party, unreceipted, invalid, future, expired, or wrong-scope claim changes a prediction | Adversarial unit and database round-trip tests |
| Abstention is meaningful | Selective risk does not decrease as coverage falls, or confidence is uncalibrated on sealed cases | Frozen chronological benchmark |
| Structured memory adds value beyond RAG | It does not beat retrieval, recent-context, static-profile, or no-personalization baselines | Same cases, same evidence boundary, sealed targets |
| Learning tracks the current user | Later corrections fail to supersede stale rules, or old evidence dominates after explicit change | Longitudinal change-event holdout |
| Deletion is complete | Any descendant remains retrievable or influences an output after source deletion | Disposable source-to-output deletion round-trip |
| Private data never influences an external adapter | The observer-indexed logical trace changes when only D1-D5 state changes | Complete egress-trace spy across requests, retries, errors, logs, and telemetry |
| Persona does not grant authority | Higher personal-fit confidence unlocks an action without a separate grant | Authorization-state transition test |

## Open mathematical gaps

- The decision-label distribution and rationale representation are not yet
  validated on a randomized represented-user sample.
- No calibrated threshold $\tau_{\mathrm{persona}}$ exists for personal
  inference.
- The relevance weights $w$ are unselected and may be unnecessary if a simpler
  deterministic order performs as well.
- Semantic conflict beyond exact or explicitly linked oppositions remains an
  annotation and evaluation problem.
- The factorization $\prod_k\phi_k$ is a candidate representation, not evidence
  that a factor graph or graph database is required.
- No scalar utility function safely combines persona fidelity, generic task
  quality, privacy, authority, and review burden. They remain a constrained
  vector objective.
- Real deletion, recovery, backup, and history-replacement evidence remains
  absent.
- The concrete independent adoption authenticator and administrator-compromise
  treatment beyond the explicit V1 threat boundary remain unselected.
- Coverage-grid values, minimum cases and clusters, minimum effect size, and
  interval level remain unfrozen; persona results therefore remain
  `not_calibrated/inconclusive`.

The next discriminating experiment is a small, source-linked, chronologically
sealed represented-user set where simple baselines, the structured core,
calibration, abstention, provenance, scope leakage, and deletion are measured
separately.
