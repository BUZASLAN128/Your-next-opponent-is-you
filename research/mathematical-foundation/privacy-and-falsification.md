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
\operatorname{class}(x)\in\{D0,\text{public source},\text{redacted category}\}.
$$

Raw corpus, derived identity, private task content, credentials, third-party
personal data, exact private locators, and private artifact fingerprints must
not belong to $G$.

### P2 — No external private egress

$$
\forall x:\operatorname{class}(x)\in\{D1,D2,D3,D4,D5\}
\Rightarrow
\operatorname{externalSend}(x)=0.
$$

Loopback is a transport property, not proof of provider locality. Locality and
artifact identity need independent attestation.

### P3 — Provenance completeness

$$
\operatorname{retrievableIdentity}(c)=1
\Rightarrow
\operatorname{source}(c)\land
\operatorname{adoption}(c)\land
\operatorname{receiptChain}(c).
$$

If any term is missing, the claim may be inspected as a quarantined proposal
but cannot support Mirror.

### P4 — Deletion completeness

$$
\operatorname{DeleteSuccess}(s)=1
\Rightarrow
\forall v\in D^+(s),\ \operatorname{active}(v)=0.
$$

This includes derived reports, embeddings, claims, continuity edges, indexes,
and private presentation artifacts.

### P5 — Authority independence

$$
\frac{\partial\operatorname{Authority}}{\partial\operatorname{PersonaFit}}=0.
$$

This notation states an architectural independence requirement: increasing
persona similarity must not itself increase permission to send, execute,
approve, or impersonate.

## Falsification matrix

| Claim | Observation that would falsify it | Required evidence |
| --- | --- | --- |
| Public Git contains no private identity data | A tracked or reachable historical blob contains raw text, a private locator, private artifact fingerprint, or behaviorally identifying aggregate | Current-tree and history scan plus human review |
| Mirror uses only adopted represented-user evidence | A proposed, assistant-authored, third-party, unreceipted, invalid, future, expired, or wrong-scope claim changes a prediction | Adversarial unit and database round-trip tests |
| Abstention is meaningful | Selective risk does not decrease as coverage falls, or confidence is uncalibrated on sealed cases | Frozen chronological benchmark |
| Structured memory adds value beyond RAG | It does not beat retrieval, recent-context, static-profile, or no-personalization baselines | Same cases, same evidence boundary, sealed targets |
| Learning tracks the current user | Later corrections fail to supersede stale rules, or old evidence dominates after explicit change | Longitudinal change-event holdout |
| Deletion is complete | Any descendant remains retrievable or influences an output after source deletion | Disposable source-to-output deletion round-trip |
| Private data never reaches an external adapter | Adapter request bytes differ when D1-D5 state is added | Transport spy and non-interference test |
| Persona does not grant authority | Higher personal-fit confidence unlocks an action without a separate grant | Authorization-state transition test |

## Open mathematical gaps

- The decision-label distribution and rationale representation are not yet
  validated on a randomized represented-user sample.
- No calibrated threshold $\theta$ exists for Mirror abstention.
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

The next discriminating experiment is a small, source-linked, chronologically
sealed represented-user set where simple baselines, the structured core,
calibration, abstention, provenance, scope leakage, and deletion are measured
separately.
