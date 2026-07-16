# Open Questions and Deep-Research Briefs

> Status: prioritized research backlog
> Last updated: 2026-07-17
> Constraint: the V1 runtime baseline is confirmed in D-025 through D-032;
> questions may challenge it with evidence but must not silently expand it.

## First-Round Answers Incorporated

The 2026-07-15 user answers resolved or narrowed several directions:

- start conceptually with a strong personality core;
- combine durable personal memory with external agent or LLM reasoning;
- target a broad mind-like scope, while the first measurable slice remains to
  be selected;
- support copilot behavior and investigate cross-conversation communication;
- preserve continuity across attempts, actions, mistakes, and outcomes;
- treat fabricated claims of reading or memory as critical failures;
- require local-first operation and adequate security;
- keep the software open source;
- accept chronological holdout evaluation;
- inspect HiveMind-Actions as the earlier prototype.

At this historical point the answers did **not** select infrastructure.
Containerized operation remained a candidate until the later implementation
authorization recorded in D-025 through D-031.

## Second-Round Answers Incorporated

| Question | Resolution | Remaining uncertainty |
| --- | --- | --- |
| RQ-001 — Mission | Confirmed as dynamic and potentially any activity of the individual | Mission hierarchy, conflicts, pause, resume, and success semantics |
| RQ-002 — Modes | Design delegated to research; explicit modes adopted as the working model | Final labels and how visible automatic transitions should be |
| RQ-003 — Capabilities | All listed capabilities are desired eventually | Authority leases, risk classes, and first-release sequencing |
| RQ-004 — Consciousness | All listed human-like functional properties are intended | Operational tests; no sentience claim is implied |
| RQ-005 — Self-improvement | Learning and persistence should be autonomous | Promotion thresholds, regression gates, rollback, and protected fields |
| RQ-006 — Corpus | Official search and export behavior was verified; availability for an authorized source remains unverified | Account type, local export, formats, counts, omissions, and other providers |
| RQ-007 — User-owned | Definition deferred for later clarification | Exact inspection, correction, deletion, portability, and provider-independence contract |
| RQ-008 — Public versus private | Confirmed: public code, private real-person identity | Treatment of synthetic and deliberately published persona fixtures |
| RQ-009 — Core | Confirmed subconscious-conscious analogy with one core | Exact boundary between core, conscious workspace, and context-specific state |
| RQ-010 — Tests | All three classes required; unknowns should trigger ask, learn, persist, and later reuse | Concrete cases can be mined from the corpus and audited by the user |

The resulting functional proposal is recorded in
[cognitive-core-hypothesis.md](cognitive-core-hypothesis.md).

## V1 Implementation Decisions Incorporated

The later plan approval and implementation instruction resolved several
questions for the bounded first experiment:

- coding judgment is the first measurable slice;
- the first surface is a local CLI;
- Python 3.12, PostgreSQL 18.4, pgvector 0.8.2, Docker Compose, and SQL edge
  tables are the V1 baseline;
- an official ChatGPT export is the first supported source adapter, but no real
  export has been inspected;
- real identity remains local and external adapters receive D0 only;
- cold start abstains or uses clearly labeled user declarations;
- a database-free Manager may begin with non-personal D0 operating memory,
  while current task context remains D1 and persona memory remains empty;
- Mirror and Advisor have no send, execute, or promotion authority;
- gpt-oss-20b and BGE-M3 are replaceable local adapter defaults, not validated
  model winners;
- god objects are prohibited and source-size, Ruff, mypy, compilation, pytest,
  PostgreSQL, and synthetic-acceptance gates are required.

The implementation checkpoint is documented in
[v1-implementation-record-2026-07-15.md](v1-implementation-record-2026-07-15.md).
The remaining questions below are scientific and operational gaps; they do not
reopen the V1 stack merely because the prototype is unvalidated.

### RQ-016 — What private-root boundary applies to each pilot surface?

**Status: answered by D-042.** Every private surface requires an explicit local
root outside Git. Review and persona inputs must also resolve inside that root.
The project makes no host-storage-product claim; identity, authority,
provenance, egress, and capability controls remain independent.

**Status update:** D-046 completed one memory-only Codex content-parser check.
Its transient contract retained no content or derived event and therefore
closed retention and deletion only for that process lifetime. Before any
evidence window, annotation, corpus ingestion, database use, or durable persona
persistence, separately approve ownership and third-party exclusions,
retention, deletion lineage, and the private artifact contract. A distinct
non-superuser runtime database role must be verified as audit-insert-only
before real database use.

### RQ-017 — Which exact model revisions fit the local runtime boundary?

**Status: one extractor candidate fits; selection quality remains open.** Live
inspection and a synthetic smoke test established that `llama-server` build
9803 can load official Qwen3-8B Q4_K_M revision
`7c41481f57cb95916b40956ab2f0b139b296d974` in the local test environment.
The exact 5,027,783,488-byte artifact and SHA-256 are pinned, the endpoint is
loopback-only with logging disabled, and one two-atom schema-constrained case
completed successfully. A later private ten-atom proposal run also completed;
its represented-user correction chain is now complete, but the selected sample
does not establish model quality.

This does not validate label precision, confidence, Turkish robustness,
prompt-injection resistance, sustained resource use, or comparison with a
1–3B extractor. The prior `openai/gpt-oss-20b` and BGE-M3 configuration values
were not tested and no embedding endpoint was started.

**Next check:** use the complete selected correction chain to define
unsupported-inference and correction-burden labels, then freeze manual labels
for a varied synthetic extraction suite;
measure exact-span validity, classification, target-layer leakage, abstention,
latency, and correction burden for this pin and one exact 1–3B pin. Do not use
any additional private source without the same explicit local-risk decision
and local-provider attestation.

### RQ-018 — What result would justify retaining the structured core?

The benchmark machinery exists, but acceptance thresholds do not. A good
average can hide attribution failure, scope leakage, stale-persona errors, or
overconfident non-abstention.

**Next check:** before opening the real holdout, define catastrophic gates and
report judgment fidelity, evidence-demand fidelity, change tracking,
calibration, abstention, and review burden separately. Failure to beat simple
baselines should trigger schema simplification, not capability expansion.

### RQ-019 — How should a data-free session produce the first persona candidate?

**Status: first real ten-atom correction chain replayed with zero pending.**
The Manager
still auto-generates only non-personal operating memory. A provisional,
unsealed interaction receipt now preserves exact available prompt and response
text, content hashes, source spans, speaker, claim holder, source authority,
source-only adoption status, subject, scope, time precision, context, and data
class. One receipt can produce multiple atomic proposals with separate speech
act, modality, classification, target layer, literal normalization, inference,
consequence, confidence dimensions, and null reasons.

The builder revalidates typed inputs, rejects mismatched spans, receipt or
subject changes, attribution laundering, dishonest data classes, missing null
reasons, and attempted confirmation or core promotion. A proposal-only local
extractor can now populate this same contract from an attested loopback model;
deterministic source-span and scope checks remain authoritative. It performs no
database write and grants no authority. Five earlier current-thread statements
produced 20 D3 proposals only in memory and their exact private mapping was
intentionally not persisted. A later fresh private receipt has now produced
ten new proposals; it is a distinct review, not a reconstruction of the
historical set.

A typed V1.2 correction receipt now supports confirmation, rejection, split,
scope narrowing, temporary validity, project-rule retargeting, inference
rejection, and a non-promoting core-review request. Partial answers preserve
pending atoms. Hash-linked replay, explicit supersession, scoped decision
projection, conflict abstention, and deletion dependency closure pass synthetic
tests without persistence or a model. This answers how the interaction can be
represented, not whether any historical or fresh interpretation is correct.

The represented user first reviewed five atoms through a sequence-one receipt,
then explicitly approved the remaining bounded batch through a linked
sequence-two receipt. The complete private state contains six split, three
rejected, one confirmed, and zero pending source atoms. Two full-chain CLI
replays agreed. The dependency-only projection contains 26 records and
performed no deletion. Because the second receipt addressed pending atoms, no
earlier decision required supersession. This is real correction-loop evidence,
not a persona claim.

**Next check:** use the
[privacy-safe correction procedure](atomic-correction-form-2026-07-15.md) to
design a larger randomized, repeat-labeled annotation pilot and measure each
action separately. Do not select a durable schema until RQ-021's round-trip and
erasure criteria are satisfied.

### RQ-020 — What is a safe user-authored Markdown declaration format?

Free-form Markdown is convenient but has no reliable per-item speaker, claim-
holder, adoption, scope, or identity-versus-control marker. Treating every
line as a confirmed preference launders assistant, third-party, quoted, or
system-control content into identity.

**Next check:** compare structured JSON with a narrowly specified Markdown
format whose front matter and per-item records carry the same explicit
authorship, adoption, plane, subject, scope, and synthetic markers. Include
quoted third-party text, assistant output, copied instructions, mixed subjects,
and malformed front matter as negative fixtures. Do not enable Markdown for
real persona import until those cases fail closed and provenance survives
persistence or the operation remains preview-only.

### RQ-021 — How should explicit adoption provenance survive persistence?

The current bootstrap table does not retain speaker, represented claim holder,
source authority, adoption, or evidence-plane fields. Converting a validated
preview declaration into that record would erase the evidence that made its
identity attribution acceptable. Real bootstrap and real replacement writes
are therefore blocked; synthetic D0 writes remain available.

**Next check:** compare explicit immutable columns with a linked, append-only
adoption receipt. The selected design must preserve source and deletion
lineage, reject legacy/unverified declarations from represented-user
retrieval, survive a write/read round trip, and support correction and erasure
without turning the audit ledger into a second corpus. Any migration is an
ask-first product decision and must be tested on a disposable database before
real use. Preserve the current rule that D0 fixtures and private identity
records cannot share a subject, including during batch ingestion and
correction.

### RQ-022 — How should identity-subject contention be retried?

The repository now avoids advisory-lock deadlock by returning
`identity_subject_busy` without partial data or audit writes. It does not yet
choose a retry budget, backoff schedule, fairness policy, or user-visible
contention behavior.

**Next check:** run a synthetic concurrent replay with opposite subject order,
bounded retry, duplicate request IDs, and forced audit failure. Measure
completion, starvation, duplicate records, duplicate receipts, latency, and
whole-operation rollback before adding automatic retries to any CLI or service.

### RQ-023 — How should semantic conflicts be exposed without model authority?

V1.2 detects opposing modalities only when applicable active decisions share
the same normalized literal and target layer. It deliberately does not treat
embedding similarity, recency, repetition, or an LLM judgment as proof that
two differently worded statements conflict.

**Next check:** construct a synthetic paraphrase and scope-overlap suite with
human-authored conflict labels. Compare exact normalization, deterministic
lexical rules, and a proposal-only local classifier. Every uncertain match
must remain visible for user review; no method may silently supersede a source
decision or cross target layers. A model adapter is justified only if it beats
the deterministic baseline without increasing false conflicts or scope leaks.

### RQ-024 — What does the first real correction batch reveal about extractor quality?

**Status: all ten selected user decisions collected through two receipts.** One
private current-thread receipt yielded ten exact-segment proposals. The first
attempt failed closed on a non-exact model span. Manual inspection of the
successful batch found interpretations that extended beyond their cited source
text. The first five actions were applied before approval and later ratified by
the user; the remaining five were authorized before application. Across the
complete selected review, six split outcomes, three rejections, and one
confirmation were recorded. Nine of ten source atoms therefore required
structural correction or rejection, but the ordered sample was not random and
is too small for a model-quality estimate.

**Next check:** freeze a larger randomized, repeat-labeled sample before
reporting precision or general correction burden. Keep confirmation, split,
rejection, scope change, and inference rejection as separate measures. Do not
treat a schema-valid atom as identity truth merely because the full receipt
chain replayed successfully.

### RQ-025 — Do the 32 blind annotation labels support a reliable real benchmark?

**Status: awaiting represented-user labels and a separate assisted-proposal
audit.** The active private pack contains
the fixed 24+8 annotation shape. A distinct bounded holdout passed its minimum
metadata-only shape in canonical rollout-filename session-start order; its
event order, dialogue, targets, and predictors remain unverified or unopened.
The label seal now rejects incomplete fields, inexact spans, identity
laundering, and unadjudicated repeat disagreement. The first complete
submission and raw repeat receipt are immutable; any disagreement is resolved
in a separately linked adjudication artifact. Its represented-user marker is a
local operator attestation, not cryptographic identity authentication.

A separate proposal-only Qwen3-8B path now preserves an unreliable primary
attempt and one linked review-ready retry. It uses two passes, deterministic
dependent fields, oversized-focus abstention, blind-repeat checks, and a fixed
review cap. The user can record compact card-number actions in resumable,
receipt-bound steps, but the assisted decisions remain empty. This path may
later estimate proposal correction burden; it cannot replace the 32-label gold
set or authorize holdout access.

**Next check:** complete and submit all 32 labels, preserve the first agreement
measurement separately
for authorship, adoption, decision, target layer, scope, evidence spans, and
abstention, adjudicate only mismatched pairs, and report exclusions without
treating them as model errors. After final sealing, open the holdout once, remove exact annotation duplicates,
freeze target-free baseline predictions, and collect represented-user targets
only afterward. Failure to retain enough independent cases must stop the
benchmark rather than relax the holdout.

## Next Discriminating Questions

These no longer ask the user to design the system from scratch. They test the
remaining boundaries exposed by the answers.

### RQ-011 — May any derived identity context reach an external reasoner?

The strictest private-core interpretation sends no raw conversation, profile,
preference, or behavioral summary to an external service. An external reasoner
would receive only explicitly allowed task information, and personalization
would happen inside the private boundary.

**Recommended default:** no raw or derived identity leaves the private
boundary. Research whether useful external reasoning remains possible under
that constraint.

**V1 resolution:** no. External adapters receive D0 public or explicitly
synthetic material only. Whether a future version can safely allow D1 is still
open and requires a separate threat-model and user decision.

### RQ-012 — What may never be changed through autonomous learning?

**Recommended protected set:** represented-person identity, read/send/tool
authority, privacy boundary, provenance rules, audit, deletion, revocation,
rollback, and safety gates. Everything else may become eligible for automatic
promotion only after evidence and regression checks.

### RQ-013 — What is the first safe authority lease?

The target includes every capability, but a first experiment still needs a
bounded authority contract.

**Recommended first evidence tier:** automatic local reading, analysis,
learning, and drafting; explicit approval for sending or state-changing tools;
no autonomous approval of another agent until independent outcome tests exist.

This is a research safety baseline, not a rejection of eventual autonomy.

**V1 resolution:** local read, analysis, private artifact write, prediction,
and proposal only. Sending, execution, approval, autonomous promotion, and
silent provider fallback are not implemented.

### RQ-014 — Which ChatGPT export route applies to the user?

Official documentation currently describes Settings export for Free, Plus,
Pro, and eligible Edu accounts, while Business and Enterprise follow different
availability rules. The account or workspace type must be known before giving
an exact acquisition procedure.

**Next check:** the user requests their own export, stores it locally outside
this Git repository, and explicitly authorizes a metadata-only inspection.

### RQ-015 — Can benchmark examples be derived instead of hand-written?

The user answered that all test classes apply; individual examples remain to
be selected. The research proposal is to mine candidate cases from chronological
history, hide the real later answer, and ask the user to audit a small balanced
sample rather than manually authoring the entire benchmark.

**Next check:** test review burden and agreement on a redacted pilot sample.

## Priority 0 — Questions That Block Responsible Corpus Work

### Q-001 — What exactly is in an authorized candidate corpus?

- Which assistants, products, accounts, exports, local histories, attachments,
  repositories, and date ranges are represented?
- Is the authorized archive mostly text, metadata, generated artifacts,
  images, logs, or duplicated data?
- Are message IDs, thread IDs, timestamps, speaker roles, model names, tool
  calls, edits, retries, and outcomes preserved?
- How much content is duplicated or derived from earlier content?

**Next discriminating check:** perform a metadata-only inventory without
copying raw content into the repository.

### Q-002 — Who owns and may process each part?

- Does the corpus include employer, customer, collaborator, or third-party
  information?
- Which sources permit export and local processing?
- Which content must be excluded, redacted, or deleted?
- What retention, revocation, and right-to-forget obligations apply?

**Next discriminating check:** create a source-by-source data governance table
before any ingestion experiment.

### Q-003 — What is the safe handling boundary?

- Must all raw processing remain local?
- Which derived artifacts are still sensitive enough to require equivalent
  protection?
- How will secrets and third-party personal data be detected?
- How will source deletion propagate into derived claims?

**Next discriminating check:** threat-model the corpus lifecycle from export
through deletion before moving data.

## Priority 1 — Product Identity

### Q-004 — What is the first measurable slice of the general virtual self?

The user confirmed a broad, mind-like long-term target. The public README
targets AI coding agents, which may still be the smallest falsifiable first
slice.

Possible first slices to compare:

- coding judgment only;
- professional knowledge-work judgment;
- general personal assistant from the beginning;
- a common personal core with separate domain-specific profiles.

**Decision criterion:** choose the smallest scope that can produce falsifiable,
safe evidence without flattening or blocking the broader target.

**V1 resolution:** coding judgment in Mirror mode. Expansion beyond that slice
remains an open product and evidence decision.

### Q-005 — What does persona mean operationally?

- Prediction of accept or reject?
- Anticipation of corrections?
- Evidence-demand prediction?
- Value and tradeoff modeling?
- Communication style?
- Delegation behavior?
- Action on the user's behalf?

**Current boundary:** prediction and review do not grant authority to act.

### Q-006 — What should the controller output?

Candidate outputs include:

- a task-specific brief;
- a critique of a plan or patch;
- predicted user objections;
- required evidence;
- applicable policies and exceptions;
- an uncertainty and abstention statement;
- provenance links.
- an explicit Mirror, Advisor or Mission, Copilot, Delegate, or Learner mode;
- source and action receipts when it claims to have read or done something.

**Next discriminating check:** test which output lets the user judge correctness
quickly without trusting an opaque score.

## Priority 1 — Signal and Schema

### Q-007 — What counts as a decision event?

- Must the user explicitly say yes or no?
- Does accepting a patch count?
- Does continuing the conversation imply approval?
- Does a later revert negate an earlier acceptance?
- Can an outcome confirm a decision the user never explicitly discussed?

**Next discriminating check:** manually label a diverse sample and measure
annotator agreement.

### Q-008 — How are reasons represented without inventing them?

- Separate stated reason from inferred reason.
- Preserve uncertainty when the user gives no rationale.
- Track alternative explanations.
- Never turn a fluent model explanation into historical fact.

**Next discriminating check:** compare extraction against manual source-linked
annotations and measure unsupported-rationale rate.

### Q-009 — How is evidence weighted?

- Explicit correction versus repeated implicit behavior.
- Recent statement versus long-running pattern.
- User preference versus verified outcome.
- One high-risk exception versus many low-risk examples.
- Independent evidence versus repeated derivatives of one source.

**Next discriminating check:** design counterexamples where frequency,
recency, explicitness, and outcome disagree.

### Q-010 — How are contradictions preserved?

- Old self versus current self.
- One role versus another.
- Exploratory idea versus committed decision.
- Global principle versus local exception.
- User statement versus observed outcome.

**Next discriminating check:** create a contradiction taxonomy before choosing
any consolidation method.

## Priority 1 — Evaluation

### Q-011 — What is the primary falsifiable claim?

Current candidate:

> Earlier conversation history can predict a later user decision, correction,
> evidence demand, and abstention need better than reasonable non-personalized
> and retrieval-only baselines.

This claim must be narrowed by domain, time range, data quality, and acceptable
error.

### Q-012 — What failure rate is tolerable?

Different errors have different cost:

- missing a preference;
- inventing a preference;
- applying the right rule in the wrong repository;
- applying an obsolete rule;
- failing to abstain;
- falsely presenting assistant text as user policy;
- acting without authority.

**Suggestion:** make false policy and scope leakage first-class metrics rather
than reporting only average prediction accuracy.

### Q-013 — How is the real user involved?

- Annotation and correction burden must remain practical.
- Evaluation should not require reading thousands of model explanations.
- The user should be able to distinguish a correct result from a persuasive
  imitation.
- Real-user acceptance should be blind to model identity where practical.

### Q-014 — What proves value beyond retrieval?

The system should outperform:

- no history;
- recent context;
- raw semantic retrieval;
- a static profile;
- a simple rule list;
- an automated judge.

The test must measure judgment and verified outcome, not merely answer recall.

## Priority 1 — Safety and User Control

### Q-015 — How does the user correct the model?

- Correct one derived claim without rewriting unrelated history.
- Narrow its scope; broader scope requires a new explicit proposal.
- mark it temporary;
- supersede rather than erase history;
- revoke it and propagate that revocation;
- inspect every source used.

### Q-016 — How does the system avoid fossilizing the user?

Candidate requirements:

- time-aware validity;
- current and historical views;
- explicit supersession;
- periodic revalidation of high-impact beliefs;
- abstention when evidence from different periods conflicts.

### Q-017 — How are authority and impersonation separated?

The project needs explicit boundaries between:

- remembering;
- predicting;
- recommending;
- reviewing;
- approving;
- communicating;
- executing.

No capability at one level should imply permission for a stronger level.

### Q-018 — How is manipulation detected?

A model that understands a user's preferences and vulnerabilities may optimize
for persuasion rather than faithful assistance.

Research must consider:

- selective evidence presentation;
- emotional targeting;
- confirmation bias;
- dependency creation;
- covert behavior shaping;
- unauthorized use by another person or agent.

## Priority 2 — Landscape and Novelty

### Q-019 — Is the integrated category genuinely novel?

Required research tracks:

- agent memory;
- personalized LLMs;
- preference learning;
- user modeling;
- human digital twins;
- computational personality;
- behavioral cloning;
- inverse decision or reward modeling;
- lifelong and temporal learning;
- personal knowledge management;
- AI governance and policy engines;
- commercial personal-AI products;
- open-source repositories;
- patents and trademarks.

The output must include negative results and close prior art, not only sources
that support novelty.

### Q-020 — What is the correct category language?

Candidates:

- personal controller;
- judgment model;
- decision persona;
- normative memory;
- personal governance layer;
- virtual-self assistant.

Research should test clarity, trust, unintended meanings, and whether the term
overpromises human equivalence.

## Priority 2 — Project and Public Contract

### Q-021 — What claims may appear in the README now?

Distinguish:

- vision;
- research hypothesis;
- planned capability;
- implemented capability;
- verified capability.

The current copy should not imply that cross-tool integrations or a working
controller already exist.

### Q-022 — What does user-owned mean?

Possible dimensions:

- local control;
- exportability;
- inspectability;
- revocation;
- deletion;
- portability across agents;
- independence from one provider;
- ability to verify derived claims;
- ability to operate without surrendering raw history.

These dimensions require explicit definitions and tests.

### Q-023 — How should bundle generation be triggered outside research tasks?

The repository script and the research AGENTS completion rule cover
substantive work governed by **research/AGENTS.md**. A script cannot independently
know when a human conversation has semantically ended.

Candidate future trigger surfaces must be compared only after their ownership
and configuration boundaries are understood. Until then, manual execution or
the scoped agent completion rule is the verified behavior.

**Next discriminating check:** use the current workflow across several tasks
and record missed or duplicate bundle runs before proposing a broader hook or
automation.

### Q-024 — Can the supplied deep-research reports be reconstructed into auditable claim maps?

The first supplied report has no bibliography. The second has numbered citation
markers without the bibliography they reference. The third is a single
physical line with named studies but no bibliography, direct URL, DOI,
resolvable citation marker, or search protocol. The fourth is much better
structured and contains three DOI strings, but still supplies no direct URL,
bibliography, claim-to-source appendix, search log, or contrary-evidence
ledger. It is possible that richer source interfaces displayed citations
separately, but that material was not supplied.

Required reconstruction fields:

- exact report claim and section;
- direct primary source and exact supporting passage, table, or experiment;
- evidence maturity and peer-review status;
- dataset, model, task, and threat-model boundary;
- contrary evidence and failed transfer assumptions;
- whether the claim is fact, author claim, inference, candidate, or decision.

**Next discriminating check:** obtain the original source lists or rerun each
research packet with mandatory inline URLs and a claim-to-source appendix.

### Q-025 — Which cognitive architecture ideas improve personal judgment prediction rather than only agent coordination?

Tri-Spirit, Global Workspace Agents, BIGMAS, JPAF, StateFactory, and RecMem
address different problems. Their existence does not show that combining them
improves one real user's decision prediction, scope control, continuity, or
abstention.

Candidate comparisons include:

- one reasoner versus a global workspace or multi-agent process;
- immediate versus delayed consolidation;
- flat retrieval versus fast-event and slow-core layers;
- behavior-derived judgment representation versus psychometric personality;
- explicit mission state versus reward or world-state factorization.

**Next discriminating check:** compare the smallest technology-neutral versions
on the same temporal holdout while measuring judgment, scope leakage,
fabricated memory, correction burden, cost, and latency separately.

### Q-026 — How are acceptance and catastrophic thresholds derived without arbitrary constants?

The second report proposed fixed values for agreement, F1, task success,
consistency, entropy, contradiction, and forgetting without a measured corpus,
error-cost model, confidence interval, or real-user acceptance protocol.

Threshold design must distinguish:

- catastrophic zero-tolerance failures such as fabricated reading receipts or
  unauthorized actions;
- risk-class-specific maximum error rates;
- baseline-relative improvement rather than isolated scores;
- confidence intervals and minimum sample sizes;
- current-user tolerance for false blocks, missed preferences, and review
  burden.

**Next discriminating check:** define the label protocol and error-cost matrix,
then estimate thresholds from a pilot temporal holdout rather than from prose.

### Q-027 — Which conversation branches are evidence even when they are not the active response path?

Extracting only an active `current_node` path may reconstruct the visible final
conversation, but abandoned branches, edits, retries, rejected answers, and
corrections may carry negative evidence and derivation history. Retaining every
branch may also increase duplication, privacy exposure, and false consensus.

**Status update:** the local Codex parser now preserves explicit parent-thread
metadata and leaves absent message-parent relations unknown. It does not yet
establish active-path semantics, edit/retry meaning, or branch-level negative
evidence.

**Next discriminating check:** use the approved private evidence-window pilot
to compare active-path-only, all-branch, and lineage-only representations
without placing raw content in the repository.

### Q-028 — Which identity dimensions can humans label without a psychometric proxy?

The newest report proposes style, personality traits, values, beliefs,
preferences, goals, relationships, skills, and metacognitive rules with one
fixed stability order. That order is not established for a real person's
judgment history.

The annotation trial must test:

- whether each category has an observable definition;
- whether value, norm, preference, belief, and temporary goal can be
  distinguished consistently;
- whether stability and scope can be labeled per claim rather than assumed
  from the category;
- whether a useful judgment model works without MBTI, Jungian weights, or
  another assigned-persona proxy.

**Next discriminating check:** write an operational glossary, double-label a
small diverse sample, and remove or merge categories with unacceptable
unsupported inference or disagreement.

### Q-029 — Which records belong to evidence, identity interpretation, and protected control?

The report's single node model combines raw message structure, epistemic
status, time validity, and cryptographic provenance. This risks turning an
extraction guess into source history or allowing learned persona behavior to
rewrite control boundaries.

Candidate separation:

- source event and receipt;
- quoted or represented actor;
- extracted claim;
- decision, correction, or supersession;
- identity candidate;
- intended action, actual action, and outcome;
- derivation and evidence-dependence edge;
- protected privacy, authority, deletion, audit, and rollback rule.

**Next discriminating check:** model ambiguous examples in one-record and
separated-record forms and compare correction, deletion, provenance, and
scope-leak failure modes.

### Q-030 — How can an outcome support learning without false causal attribution?

Reasoning-path coherence, a successful tool response, or a later project
outcome does not prove that one decision caused the result. Competing causes
include the user's intervention, another agent, environment changes, retries,
hidden selection, and luck.

The system must distinguish:

- temporal sequence from causal support;
- intended action from completed action;
- tool success from mission success;
- local success from cross-context transfer;
- observed correlation from counterfactual evidence.

**Next discriminating check:** construct outcome cases with known confounders
and measure whether the system preserves causal uncertainty instead of
promoting a fluent lesson.

### Q-031 — Which external effects are reversible, stageable, or only compensable?

The report describes all external actions as transactionally reversible. Some
local mutations may be rolled back, but a sent message, disclosed secret,
payment, publication, or third-party notification may be irreversible.

The authority model needs effect classes:

- pure read or analysis;
- reversible local mutation;
- stageable effect released only after commit;
- externally committed effect with a compensating action;
- irreversible or non-compensable effect requiring prevention or explicit
  confirmation.

**Next discriminating check:** build a synthetic effect matrix and test abort,
timeout, denial, revocation, duplicate execution, compensation, and receipt
behavior before allowing a real action surface.

### Q-032 — Can Candidate Ontology v0.1 be labeled reliably?

The fourth incoming report motivates four connected identity views:

- behavioral patterns or traits;
- value priorities and conflicts;
- autobiographical narrative and temporal continuity;
- personal metacognitive tendencies.

Human-science sources support these as useful perspectives, but not as four
mutually exclusive software stores or a complete personality ontology. Goals,
beliefs, preferences, relationships, and skills may connect differently across
periods and contexts.

**Next discriminating check:** define source-linked positive, negative, and
ambiguous examples for every proposed view; double-label a small diverse
sample; measure agreement and unsupported inference; then merge or remove
labels that cannot be applied reliably.

### Q-033 — How are personal metacognition and protected control separated?

Statements such as **I tend to ask for evidence** may describe the user.
Requirements such as **never claim an unread source was read** govern the
system regardless of whether that pattern appears in the user's history.

The model needs to distinguish:

- observed user behavior;
- inferred personal metacognitive tendency;
- explicit user instruction;
- protected privacy, provenance, authority, deletion, audit, and safety rule.

**Next discriminating check:** create adversarial examples where the inferred
user preference conflicts with a protected system rule and verify that
identity learning cannot weaken the control plane.

### Q-034 — How should source integrity coexist with deletion?

The fourth report calls raw source events immutable, while confirmed project
requirements include deletion, revocation, and propagation into derived
claims. Silent rewriting is unacceptable, but literal undeletability would
also violate the intended user-owned boundary.

Candidate distinctions include:

- retained content that is append-only or tamper-evident;
- encrypted or access-controlled content;
- deleted content replaced by a non-sensitive tombstone;
- derived claims invalidated or recomputed after source deletion;
- audit evidence that a deletion occurred without retaining the deleted
  identity-bearing content.

**Next discriminating check:** model deletion of one source that supports
several claims and compare hard deletion, cryptographic erasure, tombstoning,
and recomputation semantics without selecting a storage technology.

## Deep-Research Brief 1 — Systematic Landscape Review

### Objective

Determine whether prior academic, open-source, commercial, or patented systems
already implement all or part of the proposed personal judgment controller.

### Required Output

- search protocol and exact query families;
- databases, repositories, languages, and date range searched;
- inclusion and exclusion criteria;
- taxonomy of adjacent systems;
- claim-by-claim capability matrix;
- strongest prior art;
- negative and contradictory findings;
- reproducibility and source-quality assessment;
- safe novelty wording with confidence and limitations;
- new entries for the source ledger.

### Non-Goals

- selecting implementation infrastructure;
- treating marketing copy as verified capability;
- proving novelty from absence in one search engine.

## Deep-Research Brief 2 — Corpus Characterization

### Objective

Determine whether an authorized corpus contains enough reliable, attributable,
and ethically processable decision evidence for the project hypothesis.

### Required Output

- metadata-only source inventory;
- size by content type and source;
- message and speaker attribution quality;
- duplication and derivation estimates;
- timestamp and thread completeness;
- language and domain distribution;
- project and role separability;
- explicit versus implicit decision density;
- outcome and verification availability;
- sensitivity and third-party-data assessment;
- a safe sample-design proposal;
- blockers before any content processing.

### Safety Rule

Do not place raw corpus contents in this repository.

## Deep-Research Brief 3 — Annotation and Evidence Model

### Objective

Design and test a human-readable labeling scheme for decisions, reasons,
evidence demands, scopes, outcomes, contradictions, and uncertainty.

### Required Output

- annotation guide with positive, negative, and ambiguous examples;
- distinction between observed and inferred fields;
- agreement study;
- unsupported-inference rate;
- evidence-dependence and duplicate-source rules;
- temporal supersession examples;
- proposed revision to the decision-event hypothesis;
- list of fields that should be removed because they cannot be labeled
  reliably.

## Deep-Research Brief 4 — Benchmark and Evaluation

### Objective

Create a temporal holdout benchmark that distinguishes judgment modeling from
retrieval and persuasive imitation.

### Required Output

- falsifiable primary claim;
- train, development, and temporal test boundaries;
- leakage analysis;
- baseline definitions;
- error taxonomy;
- metrics and confidence intervals;
- real-user evaluation protocol;
- independent outcome checks;
- abstention and scope-leak tests;
- failure threshold and stop criteria;
- reproducibility package design without raw private data.

## Deep-Research Brief 5 — Privacy, Threat, and Authority Model

### Objective

Identify how raw and derived personal data could be leaked, abused,
manipulated, or used for unauthorized impersonation.

### Required Output

- asset and actor model;
- lifecycle data-flow inventory;
- abuse cases;
- consent and third-party-data issues;
- deletion and derived-data revocation requirements;
- access and authority boundaries;
- audit and user-inspection requirements;
- red-team scenarios;
- unacceptable-risk stop conditions.

## Deep-Research Brief 6 — Product Scope and Interaction

### Objective

Determine the smallest useful product behavior that lets the user inspect and
correct a judgment model without granting it unsafe authority.

### Required Output

- coding-specific versus general-persona comparison;
- target user and job-to-be-done;
- candidate controller outputs;
- review and correction interaction;
- trust and explanation requirements;
- burden on the user;
- safe shadow-mode experiment;
- explicit non-goals and authority limits.

## Deep-Research Brief 7 — Technology-Neutral Requirements

### Objective

Convert validated product and evaluation needs into requirements that can later
be used to compare infrastructure candidates.

### Required Output

- functional requirements;
- privacy and deletion requirements;
- provenance and temporal requirements;
- expected scale ranges based on measured corpus data;
- latency and cost envelopes tied to use cases;
- portability and offline requirements;
- evaluation and observability requirements;
- decision matrix template.

### Hard Boundary

Do not recommend or select infrastructure in this brief. Candidate comparison
begins only after the requirements are reviewed and explicitly accepted.

## Deep-Research Brief 8 — Personality Core, Modes, and Continuity

### Objective

Define a technology-neutral model for a persistent personality core that can
predict the user, advise toward a mission, help as a copilot, learn from
outcomes, and act only under explicit authority without confusing those
behaviors.

### Required Output

- operational definitions for personality, identity, continuity, self-model,
  memory, judgment, mission, and the user's consciousness metaphor;
- a comparison of Mirror, Advisor or Mission, Copilot, Delegate, and Observer
  or Learner modes;
- transition and permission rules between modes;
- distinction between user-authored bootstrap identity and behavior inferred
  from history;
- continuity-event and action-outcome schemas with source receipts;
- safe learning and candidate-promotion boundaries;
- one-core versus scoped-projection comparison;
- adversarial tests for fabricated reading, fabricated memory, fabricated
  outcomes, identity drift, scope leakage, and unauthorized communication;
- separately scored persona-fidelity and capability-uplift benchmarks;
- conditions that would falsify the proposed personality-core formula.

### Non-Goals

- claiming that the system is conscious;
- using AGI language as implementation evidence;
- selecting models, databases, graphs, runtimes, providers, or deployment;
- treating fluent imitation as proof of identity or continuity.

## Deep-Research Brief 9 — Private Core and External Reasoning

### Objective

Determine whether external agent or LLM reasoning can add useful capability
without exporting raw or derived identity from the user's private boundary.

### Required Output

- precise taxonomy of raw history, derived identity, task context, outbound
  message, operational metadata, and action receipt;
- threat actors, destinations, trust boundaries, and disclosure paths;
- analysis of whether summaries, embeddings, preference briefs, prompts, and
  model inputs remain identity-bearing personal data;
- candidate split between generic external reasoning and private local
  personalization;
- utility, latency, privacy, and failure tradeoffs without selecting a
  provider;
- tests for reconstruction, linkage, membership inference, cross-user leakage,
  prompt exfiltration, and covert identity transfer;
- deletion and revocation propagation across any permitted boundary;
- conditions under which external reasoning must be rejected entirely;
- measurable acceptance criteria and residual-risk statement.

### Hard Boundary

Do not upload a real persona, conversation sample, embedding, or derived
profile during this research. Use synthetic fixtures only.

## Deep-Research Brief 10 — Autonomous Consolidation and Core Stability

### Objective

Define how the system can learn and persist autonomously while retaining a
stable identity, resisting memory poisoning, and supporting inspection,
rollback, revocation, and deletion.

### Required Output

- update taxonomy for observations, episodes, facts, preferences, norms,
  skills, goals, identity claims, and authority;
- evidence requirements for candidate creation and automatic promotion;
- independence, recency, scope, contradiction, and outcome rules;
- pre-promotion replay, holdout, safety, and privacy regression gates;
- checkpoint, rollback, quarantine, canary, and supersession semantics;
- protected fields the system can never self-modify;
- poisoning, manipulation, sybil, repetition, false-outcome, and malicious-
  instruction attacks;
- forgetting, source deletion, derived-data revocation, and recovery tests;
- metrics for adaptation speed, identity drift, false promotion, stale memory,
  repeated questions, and rollback success;
- stop conditions for unsafe or unstable self-improvement.

### Non-Goals

- equating autonomy with unrestricted authority;
- choosing storage, models, frameworks, or deployment;
- optimizing average accuracy while hiding catastrophic identity or privacy
  failures.

## Suggested Research-Note Template

Use this structure for every later deep-research result:

~~~text
Research ID:
Date:
Researcher or agent:
Question:
Scope:
Non-goals:
Sources consulted:
Observed facts:
Research findings:
Contrary evidence:
Inferences and confidence:
What would falsify them:
Privacy or authority impact:
Decisions affected:
Open questions:
Next discriminating check:
~~~

## Additional Suggestions

These are candidates, not decisions:

1. Treat **negative evidence** as a first-class object. Reverts, rejected plans,
   failed tests, and withdrawn approvals may reveal judgment better than
   successful conversations.
2. Preserve a distinction between **historical self** and **current self**.
3. Design for **abstention** before optimization for confident prediction.
4. Evaluate **scope leakage** as seriously as ordinary inaccuracy.
5. Keep a visible separation between **memory**, **constitution**, and
   **authority**.
6. Require source-linked explanations short enough for the user to audit.
7. Test counterfactuals: would the predicted decision change when project,
   risk, audience, or evidence changes?
8. Design deletion so a removed source cannot survive invisibly inside derived
   policy.
9. Keep the real user in the evaluation loop but measure and minimize their
   review burden.
10. Publish capability status honestly: vision, researched, prototyped,
    implemented, and verified are different states.
### RQ-026 — What is the minimum canonical-claim gate before durable persona activation?

**Status:** Open and blocking before the reviewed annotation path can feed
Mirror or any durable cognitive core.

**Observed source conflict:** The new review and assisted-label paths preserve
represented-user authority and keep model proposals ineligible for core
promotion. The legacy Mirror path still ranks both `proposed` and `confirmed`
claim candidates and does not require represented-user claim ownership. The
first hardening checkpoint now blocks proposed, non-represented-user, inactive,
future, wrong-scope, and conflicting legacy evidence, but it does not yet
create a canonical persisted source-receipt/adoption binding for every
`ClaimCandidate`. Its database writer currently has no non-test caller, so the
remaining unsafe path is dormant rather than absent.

**Next discriminating check:** Define one typed admission contract and prove
with adversarial tests that proposed, assistant/third-party, unadopted,
unreceipted, future-valid, expired, wrong-scope, superseded, and duplicate-
origin claims cannot enter inference. Then connect exactly one reviewed source
through persist, retrieve, and erase without a second truth owner.

**Unsafe to claim yet:** Canonical-claim effectiveness, automatic promotion
safety, real-corpus benchmark quality, or product readiness before the
approved round-trip and benchmark evidence exists.
