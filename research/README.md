# Research Hub

> Status: V1.2 deterministic correction lifecycle, proposal-only local
> extractor, ephemeral Codex content parser, and bounded assisted-label review
> implemented; represented-user assisted review remains pending
> Last updated: 2026-07-16
> Infrastructure status: the V1 local CLI/runtime baseline is confirmed; one
> pinned Qwen3-8B loopback extractor has synthetic and bounded private
> proposal evidence, while assisted-review decisions, correction quality,
> model selection, and future
> integrations remain unverified.

This directory is the durable research record for **Your Next Opponent Is
You.** It preserves the originating conversation, the working product thesis,
the adjacent research landscape, candidate conceptual models, evaluation
ideas, decisions, sources, and unresolved questions.

The directory intentionally separates four kinds of material:

1. What the user actually said and approved.
2. What was directly observed in the repository or external sources.
3. What is inferred from that evidence.
4. What remains only a candidate or open question.

## Working Research Statement

The project investigates a private, user-owned cognitive core and controller
for AI agents. Persona imitation and communication fidelity are in scope, but
they are not sufficient evidence by themselves. The first measurable target is
a contextual model of how a specific user maintains continuity and evaluates
work:

- what the user accepts, rejects, corrects, or defers;
- why the user makes that decision;
- what evidence the user requires;
- which rule applies in which project, repository, path, task, role, and time;
- how later outcomes confirm, weaken, or supersede earlier conclusions.

The shortest current distinction is:

> Existing memory asks: what should the agent remember about the user?<br>
> This project asks: what would this user accept here, why, and with what proof?

## Status Snapshot

| Statement | Status | Evidence |
| --- | --- | --- |
| Private AI-conversation history is a candidate longitudinal source; no public record contains its size or content. | Confirmed source direction and privacy boundary | [Decision D-006](decision-log.md) and [public/private boundary](../AGENTS.md#public-and-private-boundary) |
| The intended system includes persona imitation and communication fidelity; V1 measures judgment fidelity first. | Confirmed direction and V1 priority | [Decision D-001](decision-log.md#d-001--prioritize-judgment-fidelity-in-the-first-measurable-slice) |
| The first product target is a strong personality core. | Confirmed direction | User answers, 2026-07-15 |
| The product should combine its durable personal memory with an external agent or LLM reasoning capability. | Confirmed behavioral requirement; permanent provider unselected | User answers, 2026-07-15 |
| The product should be local-first and open source. | Confirmed requirements | User answers, 2026-07-15 |
| The working cognitive model is one subconscious personality core plus a bounded conscious workspace. | Confirmed functional direction; technology-neutral | Second-round user answers and [cognitive hypothesis](cognitive-core-hypothesis.md) |
| Mission is dynamic and may represent any activity of the individual. | Confirmed product direction | Second-round user answers, 2026-07-15 |
| Learning and persistence should be autonomous within versioned, reversible, protected boundaries. | Confirmed behavioral direction | Second-round user answers and [decision log](decision-log.md) |
| Public code must remain separate from private raw and derived identity. | Confirmed privacy requirement | Second-round user answers, 2026-07-15 |
| V1 uses Python 3.12, PostgreSQL 18.4, pgvector 0.8.2, Docker Compose, and explicit SQL relationship tables. | Confirmed and implemented V1 decision | [Decisions D-025 through D-030](decision-log.md) and [implementation record](v1-implementation-record-2026-07-15.md) |
| All listed copilot, communication, tool, and review capabilities are desired eventually, but capability does not grant authority. | Confirmed long-term direction with open permission design | Second-round user answers, 2026-07-15 |
| Official ChatGPT documentation supports product search and eligible account export, but not a verified bulk-history API. | Research finding | [Source ledger](source-ledger.md), S-014 through S-016 |
| The first two user-supplied deep-research reports are preserved and reviewed; the second is the richer hypothesis map, but neither is accepted as architecture or scientific authority. | Research finding | [Comparative report review](report-review-2026-07-15.md) |
| The first report from the next research batch is preserved and reorganized into a technology-neutral convergence map; it strengthens the functional dependency order but does not establish its proposed stack or guarantees. | Research finding | [Round 1 synthesis](deep-research-round-01-synthesis-2026-07-15.md) and [convergence map](convergence-map.md) |
| The second report from the next research batch is the strongest ontology-and-evaluation input so far; it supports a multi-view identity candidate and sharper Mirror evaluation, but its four-view model, promotion ladder, and schema remain unvalidated candidates. | Research finding | [Round 2 synthesis](deep-research-round-02-synthesis-2026-07-15.md) and [convergence map](convergence-map.md) |
| Every later research report must be preserved, source-audited, classified, ordered, merged into the living convergence map, and converted into next discriminating checks. | Confirmed research-process decision | [Decision D-024](decision-log.md) and [research intake contract](AGENTS.md#research-report-intake-and-convergence) |
| A deterministic end-of-conversation script combines all non-ignored repository Markdown into one local generated file. | Implemented documentation utility | [Bundle workflow](#end-of-conversation-markdown-bundle) |
| The repository now contains a modular local CLI, typed contracts, migrations, private-data policy, synthetic fixtures, and a Mirror benchmark harness. | Implemented prototype; not real-person validation | [V1 implementation record](v1-implementation-record-2026-07-15.md) |
| The data-free Manager starts without history, PostgreSQL, a private root, or a model provider and generates only an ephemeral D0 system-control seed. | Implemented cold-start slice; not persona evidence | [Decision D-032](decision-log.md) and [V1 implementation record](v1-implementation-record-2026-07-15.md) |
| The persona preview projects only explicitly adopted declarations, keeps missing views visible, and performs no persistence, provider call, authority grant, or core promotion. | Implemented Layer 2 preview; declared-only and unvalidated | [Decision D-033](decision-log.md) and [progress assessment](progress-gap-assessment-2026-07-15.md) |
| The first user-facing declared-only calibration was reproduced in memory without persistence; its current-thread source receipts remain provisional and user correction is pending. | Local calibration checkpoint; not persona validation | [Conversation Event 023](conversation-record.md#event-023--delegated-decision-boundary-and-first-user-facing-calibration) and [Source L-015](source-ledger.md#l-015--delegated-decision-boundary-and-first-persona-calibration-checkpoint) |
| A provisional interaction receipt can now project one exact response into multiple span-verified atomic proposals while keeping modality, target layer, literal reading, inference, consequence, confidence, and null reasons separate. | Implemented review apparatus; non-persisted and awaiting user correction | [Decision D-036](decision-log.md#d-036--require-atomic-interaction-review-before-persona-promotion), [RQ-019](open-questions.md#rq-019--how-should-a-data-free-session-produce-the-first-persona-candidate), and [Source L-016](source-ledger.md#l-016--atomic-interaction-review-checkpoint) |
| Per-atom correction receipts now support partial review, deterministic hash-chain replay, explicit supersession, scope/time filtering, deletion dependency projection, and conflict abstention without a database or model. | Implemented V1.2 lifecycle apparatus; synthetic coverage plus one complete private two-receipt represented-user review | [Decision D-037](decision-log.md#d-037--prove-the-decision-lifecycle-before-model-integration), [Event 025](conversation-record.md#event-025--deterministic-correction-lifecycle-and-model-gate), [Source L-017](source-ledger.md#l-017--deterministic-correction-and-decision-lifecycle-checkpoint), and [privacy-safe form](atomic-correction-form-2026-07-15.md) |
| A pinned Qwen3-8B Q4_K_M endpoint can propose exact-span atoms through the same review contract while deterministic code retains scope, correction, promotion, and authority control. | Implemented proposal-only experiment; one synthetic live case, not a model-selection or persona result | [Decision D-038](decision-log.md#d-038--permit-one-pinned-local-extractor-as-a-proposal-only-experiment), [Event 026](conversation-record.md#event-026--fast-local-extractor-authorization-and-synthetic-smoke-test), and [Source L-018](source-ledger.md#l-018--pinned-proposal-only-local-extractor-checkpoint) |
| One fresh private current-thread receipt produced a bounded pending proposal set under an explicit outside-Git root; review found an interpretation that extended beyond its cited source text. | Real proposal checkpoint; correction required, not persona evidence | [Decision D-039](decision-log.md#d-039--use-an-explicit-outside-git-root-for-the-first-private-review), [Event 027](conversation-record.md#event-027--first-outside-git-real-proposal-batch), and [Source L-019](source-ledger.md#l-019--first-outside-git-real-proposal-checkpoint) |
| The first bounded batch was applied before approval and retained only after the user's explicit ratification; the private receipt replayed deterministically and preserved the remaining pending proposals. | Genuine partial correction-loop observation plus recorded assistant execution-order error; not persona accuracy or durable memory | [Decision D-040](decision-log.md#d-040--record-the-user-reviewed-first-bounded-correction-batch), [Event 028](conversation-record.md#event-028--first-genuine-user-correction-receipt-and-replay), and [Source L-020](source-ledger.md#l-020--first-represented-user-correction-and-deterministic-private-replay) |
| The user then reviewed the remaining bounded batch through a second chained receipt. The selected private review closed with no pending source atoms; two replays agreed and deletion remained projection-only. | Complete decision-chain observation for one selected review; not extractor accuracy, persona fidelity, or persistence evidence | [Decision D-041](decision-log.md#d-041--complete-the-user-reviewed-bounded-correction-chain), [Event 029](conversation-record.md#event-029--complete-the-first-private-correction-chain), and [Source L-021](source-ledger.md#l-021--complete-two-receipt-user-correction-chain) |
| D0 fixtures and private identity evidence cannot share a represented subject, cross-class corrections are rejected, and inference fails closed on contaminated legacy subjects. | Implemented transactional contamination boundary; synthetic evidence only | [Decision D-034](decision-log.md) and [threat model](v1-threat-model-2026-07-15.md) |
| Predictor inputs no longer contain hidden target fields, synthetic fixtures no longer echo their own targets, and retrieval no longer falls back to unrelated zero-overlap persona evidence. | Implemented experimental-integrity hardening; synthetic evidence only | [Progress assessment](progress-gap-assessment-2026-07-15.md) |
| The PostgreSQL 18.4 plus pgvector 0.8.2 image built and both V1 migrations ran locally on loopback. | Observed local runtime fact | [V1 implementation record](v1-implementation-record-2026-07-15.md) |
| Every real-data operation requires an explicit outside-Git root; review and persona inputs must also resolve inside it. | Implemented fail-closed path boundary | [Threat model](v1-threat-model-2026-07-15.md) and [Decision D-042](decision-log.md#d-042--make-the-explicit-outside-git-root-the-complete-local-path-gate) |
| One real local Codex metadata inventory completed outside Git without copying conversation fields, deriving claims, or calling a database or model provider. | Private runtime checkpoint; metadata map only, not corpus or persona evidence | [Inventory checkpoint](codex-metadata-inventory-2026-07-16.md), [Decision D-043](decision-log.md#d-043--authorize-a-content-free-local-codex-metadata-inventory), [Event 030](conversation-record.md#event-030--remove-the-host-storage-probe-and-inventory-local-codex-metadata), and [Source L-022](source-ledger.md#l-022--content-free-local-codex-metadata-inventory) |
| A bounded local Codex content parser completed two matching real runs in process memory while emitting and persisting no content, deriving no claim, and calling neither a database nor a model. | Private parser-feasibility checkpoint; not ingestion, annotation, persona evidence, or full-corpus readiness | [Parser checkpoint](codex-content-pilot-2026-07-16.md), [Decision D-046](decision-log.md#d-046--authorize-an-ephemeral-local-codex-content-parser-pilot), [Event 032](conversation-record.md#event-032--return-to-the-private-corpus-with-an-ephemeral-parser-pilot), and [Source L-024](source-ledger.md#l-024--ephemeral-local-codex-content-parser-pilot) |
| A private 24+8 annotation pack has immutable first-submission receipts, separate repeat adjudication, and a distinct metadata-only session-start-ordered holdout under the current schema; dialogue, targets, and predictors remain unopened. | Implemented private evaluation apparatus; awaiting labels and not persona-quality evidence | [Pilot checkpoint](persona-annotation-feasibility-pilot-2026-07-16.md), [Decisions D-048](decision-log.md#d-048--freeze-a-distinct-metadata-only-session-start-ordered-mirror-holdout) and [D-049](decision-log.md#d-049--preserve-initial-labels-and-separate-repeat-adjudication), and [Event 036](conversation-record.md#event-036--preserve-the-first-label-submission-and-remove-corpus-dependent-public-counts) |
| A proposal-only assisted-label path now runs two independent local-model passes, derives dependent safety fields in deterministic code, abstains on oversized focus text, audits blind-repeat consistency, and refuses review when the bounded burden cap is exceeded. One preserved failed attempt was followed by one linked retry that reached the configured review-ready gate; represented-user review remains pending. | Implemented private proposal checkpoint; not labels, persona quality, holdout evidence, or model selection | [Decision D-050](decision-log.md#d-050--replace-full-manual-pre-labeling-with-bounded-model-assisted-review), [Event 040](conversation-record.md#event-040--bound-model-assisted-labeling-and-preserve-the-failed-attempt), and [Source L-026](source-ledger.md#l-026--bounded-model-assisted-label-proposal-checkpoint) |
| A loopback endpoint is transport-local but is not trusted with private identity data until the operator separately attests provider locality. | Implemented fail-closed boundary; local experiment attested and first bounded private proposal run observed | [Decisions D-029](decision-log.md) and [D-038](decision-log.md#d-038--permit-one-pinned-local-extractor-as-a-proposal-only-experiment) |
| Raw user turns remain unattributed with an unknown claim holder until explicit adoption or span attribution, preventing pasted third-party text from silently becoming persona evidence. | Implemented source-authority rule | [Decision D-027](decision-log.md) |
| Qwen3-8B Q4_K_M is the first live extractor experiment; gpt-oss-20b and BGE-M3 remain untested candidates. | Local synthetic observation; no model winner selected | [RQ-017](open-questions.md#rq-017--which-exact-model-revisions-fit-the-local-runtime-boundary) and [Source L-018](source-ledger.md#l-018--pinned-proposal-only-local-extractor-checkpoint) |
| User-authored decisions and verified outcomes must carry different authority from assistant-authored context. | Confirmed decision | Originating proposal and user clarification |
| A bounded private annotation pack is retained outside Git for represented-user review; no label is complete, no real holdout dialogue or target is open, and nothing is cleared for ingestion or promotion. | Observed project state | [Annotation and holdout checkpoint](persona-annotation-feasibility-pilot-2026-07-16.md) |
| Adjacent systems cover memory, graph retrieval, personalization, and digital-twin behavior. | Research finding | [Source ledger](source-ledger.md) |
| The exact integrated product category appears underexplored in the sampled sources. | Inference, medium confidence | [Landscape](landscape.md); not an exhaustive novelty search |
| No real-person benchmark, annotation study, or user-audited temporal holdout has been run. | Observed project state | Conversation content has not been sampled for those experiments |
| Public research records must use neutral user language and attribute procedure or interpretation failures to the responsible apparatus. | Confirmed documentation policy | [Decision D-044](decision-log.md#d-044--require-neutral-and-accountable-public-research-language) and [Event 031](conversation-record.md#event-031--correct-public-record-tone-and-replace-feature-history) |
| The implemented V1 remains a scientific prototype and must not be presented as a faithful virtual self or production system. | Confirmed scope boundary | [V1 implementation record](v1-implementation-record-2026-07-15.md) |

## Documents

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Mandatory research capture, evidence, privacy, and decision rules |
| [conversation-record.md](conversation-record.md) | Complete substantive record of the originating conversation |
| [original-proposal.md](original-proposal.md) | Preserved copy of the supplied product and README proposal |
| [concept.md](concept.md) | Distilled thesis, terminology, principles, boundaries, and risks |
| [cognitive-core-hypothesis.md](cognitive-core-hypothesis.md) | Subconscious-conscious functional model, dynamic missions, modes, continuity, and autonomous consolidation |
| [convergence-map.md](convergence-map.md) | Living evidence-maturity ladder and ordered functional shape updated as research reports arrive |
| [landscape.md](landscape.md) | Comparison with adjacent memory, graph, personalization, and digital-twin work |
| [hivemind-actions-case-study.md](hivemind-actions-case-study.md) | Source-grounded review of the earlier prototype and its control-boundary lessons |
| [model-and-evaluation.md](model-and-evaluation.md) | Technology-neutral research hypothesis for extracting and testing a judgment model |
| [source-ledger.md](source-ledger.md) | Consulted sources, evidence types, findings, and limitations |
| [decision-log.md](decision-log.md) | Explicitly confirmed, candidate, rejected, and still-open decisions |
| [open-questions.md](open-questions.md) | Prioritized research questions and deep-research briefs |
| [deep-research-prompts.md](deep-research-prompts.md) | Ten standalone, copy-ready research packets with shared evidence rules |
| [report-review-2026-07-15.md](report-review-2026-07-15.md) | Comparative audit of the first two returned reports, selected primary sources, quarantined claims, and reusable hypotheses |
| [deep-research-round-01-synthesis-2026-07-15.md](deep-research-round-01-synthesis-2026-07-15.md) | Ordered synthesis and primary-source audit of the first report in the next research batch |
| [deep-research-round-02-synthesis-2026-07-15.md](deep-research-round-02-synthesis-2026-07-15.md) | Plain-language judgment, candidate identity ontology, and primary-source audit of the second report in the next research batch |
| [v1-implementation-record-2026-07-15.md](v1-implementation-record-2026-07-15.md) | Confirmed V1 boundary, implemented modules, local runtime evidence, scientific status, and remaining gates |
| [v1-threat-model-2026-07-15.md](v1-threat-model-2026-07-15.md) | V1 protected assets, trust boundaries, threat controls, required evidence tiers, and stop conditions |
| [progress-gap-assessment-2026-07-15.md](progress-gap-assessment-2026-07-15.md) | Layer 0-8 implementation-versus-evidence matrix, competing hypotheses, corrected gaps, and next discriminating sequence |
| [atomic-correction-form-2026-07-15.md](atomic-correction-form-2026-07-15.md) | Git-safe 20-slot correction control record; private atom content and runtime identifiers remain local |
| [codex-metadata-inventory-2026-07-16.md](codex-metadata-inventory-2026-07-16.md) | Public contract, privacy boundary, result qualification, and next step for the private local metadata inventory |
| [codex-content-pilot-2026-07-16.md](codex-content-pilot-2026-07-16.md) | Content-free public record of the bounded, memory-only real Codex parser checkpoint and the next annotation gate |
| [persona-annotation-feasibility-pilot-2026-07-16.md](persona-annotation-feasibility-pilot-2026-07-16.md) | Current 24+8 label contract, metadata-only protected holdout, synthetic baselines, real aggregate evidence, and remaining user-label gate |
| [persona-etiketleme-kilavuzu-tr.md](persona-etiketleme-kilavuzu-tr.md) | Özel 24+8 etiketleme paketi için Türkçe adımlar, sabit değer sözlüğü ve kör tekrar uzlaştırma akışı |
| [incoming-reports/](incoming-reports/README.md) | User-supplied inputs preserved verbatim when safe or hash-linked and redacted when identity-bearing; all remain non-authoritative |

## End-of-Conversation Markdown Bundle

Run the repository script after a substantive project-research conversation:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/export-all-markdown.ps1
~~~

It writes **exports/your-next-opponent-is-you-all-markdown.md** and combines
every tracked or non-ignored untracked Markdown source visible to Git. Sources
are ordered by repository-relative path and wrapped in explicit file
boundaries. The output is deterministic, excluded from its own input, and
ignored by Git so the repository does not store a second competing copy of all
research.

The bundle is a transport and reading artifact, not a source of truth. Edit the
individual Markdown files, then regenerate it.

## Current Product Boundaries

The current research and V1 implementation explicitly do not define the
product as:

- a voice, tone, or vocabulary clone as the sole success criterion;
- a transcript search wrapper;
- an unscoped collection of user facts;
- unbounded, unaudited, or irreversible self-modification;
- action authority granted solely from persona similarity;
- a claim that every past statement remains true forever;
- a product tied to a single agent, model, provider, or editor;
- a public repository containing a real person's raw or derived identity;
- an implemented capability merely because it appears in a conceptual diagram.

## Research Discipline

- Raw conversations are evidence, not memory.
- Assistant output is context, not user truth.
- A correction is evidence for a possible rule, not automatic policy.
- Context, time, provenance, confidence, and outcome must survive extraction.
- Contradictions are research data, not cleanup noise.
- The current user must be able to inspect, correct, revoke, and supersede
  derived claims.
- Novelty, quality, and safety require separate evaluation.

## Starting Point for the Next Researcher

Read the files in the order listed below:

1. [AGENTS.md](AGENTS.md)
2. [conversation-record.md](conversation-record.md)
3. [decision-log.md](decision-log.md)
4. [concept.md](concept.md)
5. [cognitive-core-hypothesis.md](cognitive-core-hypothesis.md)
6. [convergence-map.md](convergence-map.md)
7. [landscape.md](landscape.md)
8. [hivemind-actions-case-study.md](hivemind-actions-case-study.md)
9. [source-ledger.md](source-ledger.md)
10. [model-and-evaluation.md](model-and-evaluation.md)
11. [open-questions.md](open-questions.md)
12. [deep-research-prompts.md](deep-research-prompts.md)
13. [report-review-2026-07-15.md](report-review-2026-07-15.md)
14. [deep-research-round-01-synthesis-2026-07-15.md](deep-research-round-01-synthesis-2026-07-15.md)
15. [deep-research-round-02-synthesis-2026-07-15.md](deep-research-round-02-synthesis-2026-07-15.md)

16. [v1-implementation-record-2026-07-15.md](v1-implementation-record-2026-07-15.md)
17. [v1-threat-model-2026-07-15.md](v1-threat-model-2026-07-15.md)
18. [progress-gap-assessment-2026-07-15.md](progress-gap-assessment-2026-07-15.md)
19. [atomic-correction-form-2026-07-15.md](atomic-correction-form-2026-07-15.md)
20. [persona-annotation-feasibility-pilot-2026-07-16.md](persona-annotation-feasibility-pilot-2026-07-16.md)

Then record new sources, negative evidence, questions, and decisions according
to the local documentation contract. Do not treat an implemented mechanism as
scientific validation or silently expand the confirmed V1 baseline.
