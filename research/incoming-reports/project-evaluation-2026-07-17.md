# Supplied Project Evaluation — 2026-07-17

> Intake date: 2026-07-17
>
> Supplied title: `Your Next Opponent Is You — Proje Değerlendirmesi`
>
> Report snapshot date: 2026-07-16
>
> Reported repository commit: `701c67b2a992e9884393a7de1cfd02a65d2354c0`
>
> Supplied artifact SHA-256:
> `62A68EFE858E6758B6A3DD806B0052C13A6D044E81A666B99F4CEB429CF9668D`
>
> Provenance: user-supplied output from another AI system
>
> **Authority: none**

This is a normalized preservation of the supplied report. Repetition and UI
chrome were removed, but every distinct finding, prescription, limitation, and
question was retained. The report is evidence to audit, not a project
decision.

## Report Verdict

The report calls the frozen commit a research prototype that can be shared
after revisions, but not a product or real-data pilot. It identifies epistemic
discipline as the repository's strongest asset: separation of fact,
inference, candidate, and decision; provenance; negative evidence;
falsifiability; privacy classes; and explicit no-action authority. It says the
central hypothesis—whether a structured personal cognitive core predicts
future coding judgments better than simpler baselines—has not yet been tested.

The report recommends freezing new agent or architecture features until the
canonical claim path, benchmark integrity, provenance-erasure closure, and a
small annotation pilot are complete. Product investment should depend on
measurable lift over equally budgeted baselines.

## Preserved Findings

1. **Legacy claim authority:** `PROPOSED` and assistant-originated candidates
   may affect Mirror output without represented-user confirmation, explicit
   adoption, or a correction receipt.
2. **Disconnected real path:** the atomic review path remains file-based while
   the legacy candidate table feeds Mirror; no non-test caller persists claim
   candidates through a complete ingest-to-retrieval chain.
3. **Synthetic benchmark only:** `BenchmarkCase` accepts only D0 synthetic
   cases, so the central real-user claim cannot be tested by the current CLI.
4. **Temporal leakage:** benchmark clusters are ordered by their maximum time;
   a cluster spanning a boundary can place an older event in the sealed side
   without enforcing `max(development) < min(sealed)`.
5. **Broad database role:** the runtime grant script permits direct DML on all
   protected tables except narrower revocations for migrations and audit.
6. **Incomplete deletion:** some review and correction outputs are written to
   disk while their deletion result remains a projection; a shared artifact
   registry and verified cascading deletion are absent.
7. **Nominal fatal gates:** predictions can name a fatal gate, but executable
   detectors and mandatory fail-closed orchestration are absent.
8. **No empirical center-claim result:** extractor precision and recall,
   inter-annotator agreement, real temporal holdout, calibration, and
   user-level uncertainty have not been measured.
9. **Target isolation gap:** predictor inputs omit target fields, but complete
   case artifacts and evidence receipts do not form a physically separate,
   cutoff-bound target vault.
10. **Scope and lineage gap:** the report claims validity handling is
    incomplete and notes that derivation edges have no insertion path.
11. **Weak baseline semantics:** current baselines rely on case-local
    `decision:<label>` markers; structured-core behavior is not a learned
    personal core, confidence is fixed, and abstention is not modeled as a
    separate cost-sensitive action.
12. **Delivery evidence gap:** the frozen snapshot lacked GitHub Actions,
    current PostgreSQL acceptance evidence, and a PR description tied to HEAD.

## Report's Proposed Gates

1. **Core safety:** one canonical claim model; only represented-user,
   confirmed, explicitly adopted, receipt-bound evidence may influence
   inference. Quarantine proposals and bind source and derivation edges.
2. **Benchmark instrument:** enforce the temporal invariant, isolate targets,
   implement fatal-gate detectors, and bind code, prompt, model, metric, and
   environment revisions into the protocol hash. Pre-register endpoint,
   minimum effect, leakage limit, and accept/reject rule.
3. **Annotation pilot:** two independent annotators plus represented-user
   adjudication; measure exact-span validity, precision/recall, agreement,
   correction burden, and disagreement taxonomy.
4. **Provenance and forgetting:** demonstrate one complete
   ingest-to-erase round trip with derivation edges, expiry, cascade, and a
   verified receipt; narrow runtime database operations.
5. **Blind temporal experiment:** compare zero-history, declared profile,
   recent context, retrieval/rules, and structured core under equal budgets;
   report selective risk, calibration, abstention coverage, user-cost loss,
   and user-level confidence intervals.
6. **Product discovery:** invest in onboarding and retention only if the blind
   experiment shows meaningful lift. Treat licensing as later product-model
   work.

## Report Questions

- What initial setup and correction burden is acceptable per user?
- Which technical decision classes provide a valuable and safe first wedge?
- What user-level lift over a strong retrieval baseline is meaningful?
- How should false representation, abstention, and correction costs be
  weighted?
- Which threat model and deployment environment define deletion and retention
  promises?
- Is the intended outcome a research artifact, self-hosted tool, or commercial
  platform?

## Local Claim Audit Against Current HEAD

The report is stale by construction: it inspected `701c67b`, while this audit
checked `fbcbb0b`. The later branch adds the private annotation study,
protected holdout apparatus, bounded Qwen3-8B proposal sidecar, immutable retry
chain, D2 artifact correction, and additional tests. Those later changes do
not close persona quality or the central benchmark claim.

### Confirmed against source

- Legacy candidate retrieval accepts both `proposed` and `confirmed` and does
  not require represented-user claim ownership in the selection function.
- The persistence method for claim candidates has no non-test caller.
- The benchmark remains D0-only and its cluster split lacks a strict
  cross-boundary event-time invariant.
- Fatal gates are aggregated when supplied, but no mandatory detector layer
  creates them.
- The runtime database grant remains broad.
- `derivation_edges` is traversed and deleted but has no insertion path.
- The PR description was tied to an older commit and test count.

### Partially stale or overstated

- The persona-study store now enforces bounded on-access expiry and deletion
  for its own artifacts. The older interaction-review deletion path remains
  projection-only, so the general deletion gap is reduced but not closed.
- Legacy core checks candidate and declaration expiry through selected
  `valid_until` fields. It still does not apply `valid_from` or the existing
  shared scope-time evaluator consistently, so a narrower temporal-validity
  finding remains valid.
- Local provider identity is explicitly configured and operator-attested in
  the newer assisted-label command, but it is not cryptographically bound to
  the live process. The report's stronger runtime-attestation concern remains
  open.

### Important qualification

The unsafe legacy candidate path is currently dormant because no production
caller writes claim candidates. This reduces immediate runtime exposure but
does not make the contract safe. It must be closed before the reviewed
annotation path is connected to durable core retrieval.

## Verification and Falsification

The highest-priority finding is falsified only if inference demonstrably
rejects proposed, non-user, unadopted, unreceipted, future-valid, expired, or
wrong-scope claims before ranking, with adversarial tests and a single
production persistence path. Benchmark concerns require an immutable real-data
protocol whose sealed events are all later than development events and whose
predictor cannot access targets or post-cutoff evidence. Deletion claims
require a real round trip proving source and all derivatives are absent or
tombstoned according to a declared threat model.

## Intake Disposition

The report strengthens the decision to keep real holdout scoring, automatic
promotion, and product claims closed. It does not select infrastructure or
authorize real-data ingestion. The next architecture task should be a separate
Gate 0 canonical-claim safety change, not an unreviewed expansion of the
assisted-label checkpoint.
