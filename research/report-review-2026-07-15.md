# Review of the First Two Deep-Research Reports

> Date: 2026-07-15
> Status: research finding and claim audit
> Decision effect: no infrastructure, license, provider, storage, protocol, or
> acceptance threshold is promoted by this review

## Question

Which parts of the first two user-supplied reports should influence the
project, and which parts must remain unverified candidates?

The review distinguishes four different judgments:

1. whether a report understands the product;
2. whether it contributes new and useful hypotheses;
3. whether its external claims are traceable and correctly scoped;
4. whether it is safe to use as design authority.

A report can be excellent on the first two and still fail the last two.

## Inputs and Provenance

### R-001 — Product design and launch report

- **Preserved input:**
  [Product Design and Launch](incoming-reports/product-and-launch-report-2026-07-15.md)
- **Type:** User-supplied AI research report.
- **SHA-256:**
  `632D843C5E6E2FB94C5CD584D17A2E1240D29CC7A260BF630B71E0702C25FF0A`
- **Observed limitation:** The supplied artifact names many papers,
  frameworks, standards, laws, and benchmarks but contains no direct URL, DOI,
  bibliography, numbered source record, access date, or search log.

### R-002 — Autonomous personal cognitive core report

- **Preserved input:**
  [Autonomous Personal Cognitive Core Systems](incoming-reports/autonomous-personal-cognitive-core-report-2026-07-15.md)
- **Type:** User-supplied AI research report.
- **SHA-256:**
  `F1740E42B72A1664A6C259CCD914AE44248770B8DD5EFD45F701CEEA38F0769A`
- **Observed limitation:** The supplied artifact contains citation markers such
  as `[cite: 38]` and `[cite: 48, 49]`, but the bibliography those markers
  require is absent. It also omits exact queries, result counts, exclusion
  reasons, patent records, commercial-product records, and negative search
  results despite calling the work systematic.

The reports are preserved as content-equivalent incoming evidence with line
endings and non-semantic trailing whitespace normalized. Preservation does not
promote their recommendations or claims.

## Executive Judgment

The user's first impression is directionally correct:

- **R-001 is primarily a product and launch synthesis.** It is coherent,
  readable, and useful for positioning, threat categories, candidate lifecycle,
  and MVP discussion. Much of its strongest content restates the existing
  project research in more polished product language. It is not an independent
  research result and it silently decides open product, infrastructure, and
  licensing questions.
- **R-002 is substantially richer as a hypothesis generator.** Its mission
  conflicts, two-speed learning analogy, memory-poisoning controls, authority
  lattice, mode-specific evaluation, and public/private artifact boundary give
  the project more material to test. A targeted check found that many of its
  unusual named works are real. However, the report transfers narrow paper
  results into universal product rules, supplies arbitrary thresholds, calls a
  work-in-progress protocol a standard, and selects unconfirmed technologies.

The resulting decision is:

> Keep R-001 as an unverified product brief. Keep R-002 as an unverified
> research map. Use neither as architecture or scientific authority. Extract
> hypotheses from R-002 first, then re-source and test them claim by claim.

This is not a rejection of R-002. It is the distinction between a valuable map
and verified terrain.

## Comparative Scorecard

Scores are purpose-specific because one blended number would conceal the main
difference.

| Dimension | R-001 | R-002 | Interpretation |
| --- | ---: | ---: | --- |
| Understanding of the existing product thesis | 8.5/10 | 8.0/10 | Both ingest the project direction well |
| New conceptual contribution | 5.0/10 | 8.5/10 | R-002 contributes more research candidates |
| Product communication value | 8.0/10 | 5.5/10 | R-001 is the stronger positioning brief |
| Source auditability in the supplied artifact | 2.0/10 | 2.5/10 | R-002 has citation markers, but no resolvable bibliography |
| Claim calibration | 5.0/10 | 3.5/10 | R-002 converts local results into broad guarantees more often |
| Compliance with the infrastructure decision gate | 3.0/10 | 2.0/10 | Both silently promote open candidates |
| Usefulness as an idea backlog | 7.0/10 | 8.5/10 | Both are useful when stripped of authority |
| Readiness as an evidence-backed design | 4.0/10 | 4.0/10 | Neither is ready without reconstruction and validation |

## R-001: What It Gets Right

R-001 correctly reinforces several confirmed project directions:

- judgment and correction modeling is more important than voice imitation;
- assistant output is context while user decisions and verified outcomes carry
  different candidate authority;
- transcript content must not become policy merely because it was retrieved;
- candidates need provenance, scope, time, conflict, evaluation, versioning,
  and rollback;
- memory poisoning and authority creep are first-class risks;
- public software must remain separate from a real person's private history and
  derived identity;
- temporal replay, holdout evaluation, counterexample search, shadow behavior,
  and real outcomes are stronger than fluent imitation;
- correction burden, objection prediction, false blocking, scope precision,
  deletion propagation, and leak detection are useful metric families.

Its provenance-field list, signal classes, candidate lifecycle, risk/evidence
matrix, and public/private release boundary are directly reusable as research
inputs after their status is changed from prescription to candidate.

## R-001: Where It Overreaches

### Circularity rather than independent validation

The report repeats exact concepts already present in the supplied project
context, including the private core, limited workspace, capability-versus-
authority boundary, sourced/scoped/testable/versioned/reversible envelope, and
public-code/private-mind rule. Alignment is valuable, but it does not count as
independent evidence for those concepts.

### Premature product and infrastructure decisions

R-001 presents the following as preferred or settled even though they remain
open:

- coding-agent controller as the permanent category and initial scope;
- final brand copy, repository slug, and command-line name;
- particular controller components and adapter transport direction;
- desktop or command-line deployment plus encrypted synchronization;
- a hosted or enterprise phase;
- an AGPL core with more permissive adapter surfaces;
- a fixed milestone sequence and customer segmentation.

These may be compared later, but they cannot enter the decision log through a
research report.

### Missing cognitive-core behaviors

R-001 narrows the broader mind-like target into a coding-agent governance
engine. It gives insufficient treatment to dynamic missions, visible operating
modes, autobiographical continuity, unknown-to-learning behavior, restart
reconstruction, and the metacognitive provenance/uncertainty/privacy/authority
guardian.

### Unsupported interpretation of operational silence

A commit, successful test, merge, or lack of later revert is useful outcome
evidence. It is not automatically stronger authority than an explicit user
decision. The actor, review context, later discovery window, and competing
causes must remain visible. Silence cannot be promoted into approval.

### Legal and security certainty

The GDPR and security sections are useful issue inventories, not legal or
architectural conclusions. Jurisdiction, processing role, lawful basis,
workspace ownership, third-party data, and real lifecycle behavior must be
established before turning general principles into controls.

## R-002: What It Adds

R-002's most useful additions are structural rather than technological:

1. **Architecture capability matrix.** Comparing retrieval, judgment,
   improvement, continuity, delegation, and failure in separate columns is a
   strong landscape-review format.
2. **Two-speed learning.** A fast event layer and slower durable core fit the
   subconscious/workspace hypothesis, provided recurrence is treated only as a
   trigger for review and not as evidence of truth or authority.
3. **Mission conflict taxonomy.** Resource, logical, and temporal conflict are
   useful starting categories for the dynamic mission stack.
4. **Origin-preserving transformations.** Derived summaries must inherit the
   trust and authority limits of their inputs rather than laundering them.
5. **Authority lattice.** Read, draft, tool use, delegation, and external action
   should have distinguishable, attenuating, expiring, revocable grants.
6. **Execution graph versus authority graph.** What code ran and why it was
   authorized are separate evidence chains.
7. **Mode-specific evaluation.** Mirror, Advisor, Copilot, Learner, and Delegate
   should not share one blended success metric.
8. **Public/private artifact matrix.** Schemas and synthetic fixtures can be
   public while real history, derived identity, and raw diagnostic content
   remain private.

These are candidate research contributions. They do not select their
implementation.

## Targeted Primary-Source Audit of R-002

The review checked whether several unusual names in R-002 correspond to real
works. This was a claim-existence audit, not a reproduction of their results.

| Report reference | Primary source observed | What the source actually supports | What R-002 must not infer |
| --- | --- | --- | --- |
| Tri-Spirit | [Rethinking AI Hardware](https://arxiv.org/abs/2604.13757), 2026 preprint | A planning/reasoning/execution decomposition evaluated in a simulation of heterogeneous compute | Its reported latency and energy gains do not validate a personal identity core |
| GWA | [Theater of Mind](https://arxiv.org/abs/2604.08206), 2026 preprint | An event-driven multi-agent global-workspace proposal with entropy-based coordination | It does not establish autobiographical continuity, consciousness, or the report's 30% contradiction gate |
| BIGMAS | [Brain-Inspired Graph Multi-Agent Systems](https://arxiv.org/abs/2603.15371), 2026 preprint | Dynamic multi-agent topology and a shared workspace on puzzle-style reasoning tasks | Puzzle improvements do not validate persona fidelity or long-term identity |
| JPAF | [Structured Personality Control and Adaptation](https://arxiv.org/abs/2601.10025), 2026 preprint | A preliminary Jungian/MBTI-based personality-expression framework | Questionnaire alignment is not evidence for one real user's decision persona, authority, or values |
| StateFactory | [Reward Prediction with Factorized World States](https://arxiv.org/abs/2603.09400), 2026 preprint | Hierarchical object-attribute world states for reward prediction on agent environments | World-state factorization does not validate the proposed human identity classification schema |
| RecMem | [Recurrence-based Memory Consolidation](https://arxiv.org/abs/2605.16045), ACL 2026 Findings | Delaying LLM consolidation until semantic recurrence can reduce construction cost on memory benchmarks | Recurrence does not make a preference true, user-authored, current, global, or safe to promote |
| P3 | [Client-Side Retrieval-Augmented Modification](https://arxiv.org/abs/2601.17569), 2026 preprint | On three LaMP-QA datasets, the authors report a particular client/server method recovering 90.3–95.7% of one leaky upper-bound utility with 1.5–3.5% marginal leakage under their tests | Those figures are not universal privacy or quality guarantees for this project, its corpus, or arbitrary tasks |
| TMA-NM | [Origin-Bound Memory Authority](https://arxiv.org/abs/2606.24322), 2026 preprint | A formal and benchmarked proposal for non-malleable origin-bound authority under the paper's threat model | Origin binding proves neither semantic truth nor correct scope; the single preprint still requires independent scrutiny and reproduction |
| AIP and IBCT | [AIP preprint](https://arxiv.org/abs/2603.24775) and [individual IETF draft](https://www.ietf.org/archive/id/draft-prakash-aip-00.html) | A proposal for identity, attenuated authorization, and provenance across delegated agent calls | It is not an adopted standard; the IETF text explicitly labels it work in progress |
| DPRF | [Dynamic Persona Refinement](https://arxiv.org/abs/2510.14205), in-submission preprint | Iterative persona-profile refinement against human behavior in selected role-playing tasks | It does not establish safe autonomous core rewriting, source authority, or cross-domain generalization to this user |
| MINJA | [Memory Injection Attacks](https://papers.neurips.cc/paper_files/paper/2025/hash/42a97bbd9844d2bf68596730af80bcdf-Abstract-Conference.html), NeurIPS 2025 | Query-only interactions can poison retrievable agent memory | One attack does not by itself select the project's entire memory defense architecture |
| eTAMP | [Environment-Injected Memory Poisoning](https://arxiv.org/abs/2604.02623), 2026 preprint | Environmental observations can poison later web-agent behavior across sessions | Its web-agent attack rates are not a universal risk probability for this product |

**Research finding:** R-002 is not a wholesale hallucination. Many named works
exist, and several are highly relevant. Its central evidence failure is
traceability and transfer validity: it does not show which exact source supports
each claim, and it moves from limited experiments to product-wide mandates
without an intervening argument or test.

## R-002: Critical Reasoning Errors

### Provenance is not truth

A cryptographic origin or immutable lineage can show where an item came from
and whether its recorded chain changed. It cannot prove that the statement is
true, current, correctly interpreted, authored by the represented user, or
applicable in the present scope.

### Integrity structures do not perform semantic reasoning

A Merkle tree can support tamper evidence or membership proofs. It does not
detect a semantic contradiction and does not decide that rollback is correct.
Conflict detection, policy evaluation, checkpoint selection, and rollback are
separate behaviors.

### A valid signature is not valid authority

A signature can validate a token's issuer and integrity. It cannot show that
the issuer had the right to grant the action, that the natural-language request
was correctly compiled, that the grant was not excessive, or that the external
effect matched the request. Delegate evaluation requires semantic and outcome
checks in addition to cryptography.

### Repetition is not independent evidence

Recurrence may identify material worth consolidating. Repeated derivatives of
one assistant suggestion, copied statements, or coordinated sources cannot be
counted as independent support. Frequency alone must never promote a core
belief.

### Redaction is not anonymity

Regular expressions and named-entity recognition can help detect known
patterns, but neither can guarantee removal of secrets, third-party identity,
relationships, rare attributes, or re-identification clues. A masked summary
may still be derived identity.

### Active-branch extraction can destroy negative evidence

Following only a conversation's current node may be useful for reconstructing
one visible response path, but abandoned branches, edits, rejected outputs, and
corrections may contain lineage and negative evidence. The correct corpus policy
cannot be chosen before a real export is inspected.

### Global identity values fossilize context

R-002 defines identity values as global across projects and time. That conflicts
with the project's time-aware, role-aware, context-aware model and creates a
scope-leak risk. Even a stable value needs exceptions, evidence, historical
versions, and a present validity rule.

## Quarantined Numbers

The following report values are not accepted as thresholds or measured project
results:

- overall system confidence `0.90`;
- Fleiss' kappa `0.80` as an automatic field-rejection rule;
- GWT contradiction rate `30%`;
- old-rule damage `5%` for the CLS analogy;
- BDI recovery `50%`;
- mission entropy `H(X) > 1.5`;
- Mirror agreement `85%`;
- Advisor `F1 = 0.75`;
- Copilot success `90%`;
- Learner consistency deviation `< 0.15`;
- the P3 paper's `1.5–3.5%` leakage and `95.7%` utility figures when applied
  outside that paper's datasets and protocol.

Numbers become gates only after the target behavior, sample, label protocol,
baseline, error cost, confidence interval, and real-user acceptance rule are
defined. Mathematical notation does not create empirical grounding.

## Technology and Policy Selections That Remain Unconfirmed

Neither report changes the status of:

- SQLite, vector stores, graph stores, or any hybrid data layout;
- regular-expression or named-entity-recognition libraries;
- a particular local verifier model or local/cloud token protocol;
- P3, TMA-NM, AIP, IBCT, Biscuit, Datalog, Merkle trees, MCP, or A2A;
- command-line, desktop, container, hosted, or synchronization topology;
- AGPL versus split licensing;
- final product category, command name, release phases, or market segments.

Each can be researched as a candidate only after requirements and selection
criteria are approved.

## Candidate Formula Refined by the Review

R-002 strengthens the case for a conjunctive promotion gate rather than one
opaque confidence number. The following is a technology-neutral candidate, not
a finalized formula:

~~~text
EligibleForCore(candidate) =
    source_receipts_valid
    AND speaker_authority_valid
    AND scope_fit_established
    AND temporal_validity_established
    AND dependencies_independent_enough
    AND high-impact_contradictions_resolved
    AND outcome_or_explicit_support_sufficient
    AND temporal_holdout_beats_required_baselines
    AND provenance_privacy_authority_tests_pass
    AND checkpoint_audit_rollback_ready
~~~

Any failed protected condition blocks promotion regardless of average score.
The later corpus and evaluation research must define which remaining terms can
be probabilistic, which must be deterministic, and which require the current
user.

This formula preserves R-002's strongest insight—multiple independent safety
boundaries—without importing its arbitrary constants or technologies.

## Recommended Disposition

### Preserve

- both supplied reports as content-preserved incoming research inputs;
- the product framing, threat inventory, candidate lifecycle, and metric
  families from R-001;
- the capability matrix, two-speed learning hypothesis, mission conflicts,
  origin-preserving derivation, authority lattice, mode-specific evaluation,
  and public/private artifact matrix from R-002.

### Reject as current authority

- every uncited empirical or legal claim;
- every fixed numerical threshold;
- every infrastructure or protocol selection;
- MBTI or Jungian weights as the personality-core definition;
- recurrence as sufficient evidence for consolidation;
- cryptography as proof of semantic truth or correct authorization;
- any claim that masked external reasoning has a fixed low leakage rate;
- the claim that AIP is an established standard;
- any global novelty, AGI, consciousness, or readiness implication.

### Next discriminating work

1. Obtain the missing bibliography and research trace from the report generator
   if available.
2. Build a claim-to-source matrix at paper-section level, including contrary
   findings and evidence maturity.
3. Separate architectural metaphors from behaviors that can be annotated and
   measured on the real corpus.
4. Derive thresholds from a temporal holdout, baseline comparison, error-cost
   analysis, and real-user review rather than choosing them in prose.
5. Run a technology-neutral threat model before comparing storage, protocols,
   models, or local/cloud topologies.
6. Preserve alternate conversation branches and source dependencies until a
   corpus audit shows what they contain.

## Remaining Uncertainty

- The attachments may have been copied from a richer interface that displayed
  citations separately. The supplied artifacts do not contain that missing
  material, so it cannot be treated as inspected.
- This review confirmed the existence and abstract-level scope of selected
  primary sources. It did not reproduce their code, inspect every appendix,
  verify every benchmark, or perform a systematic novelty review.
- No real user corpus, annotation sample, or runtime exists yet. Therefore no
  cognitive architecture, promotion policy, or evaluation threshold has been
  empirically validated for this project.

## Decision Record Effect

No confirmed product decision is added or changed. The user's favorable view
of R-002 is recorded as a user assessment, while the report's proposed
technologies and thresholds remain candidates pending explicit decisions and
evidence.
