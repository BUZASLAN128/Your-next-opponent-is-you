# Decision Log

> Last updated: 2026-07-16
> Promotion rule: only explicit user approval can convert a candidate into a
> confirmed decision.

This log prevents research findings, attractive ideas, or agent suggestions
from silently becoming product authority.

## Confirmed Decisions

### D-001 — Prioritize judgment fidelity in the first measurable slice

- **Date:** 2026-07-15
- **Status:** Confirmed decision
- **Decision:** The system should model how the user evaluates decisions,
  corrections, tradeoffs, and evidence. Evidence-bounded communication and
  persona imitation also remain part of the requested product direction. V1
  prioritizes judgment fidelity as its first measurable target; this does not
  remove imitation from the longer-term goal.
- **Basis:** The user explicitly clarified that the goal is persona-level
  understanding derived from conversation history and agreed with the
  distinction between memory and judgment.

### D-002 — Preserve the authority boundary between user and assistant

- **Date:** 2026-07-15
- **Status:** Confirmed decision
- **Decision:** Assistant messages provide context. User decisions,
  corrections, rejections, explicit requirements, and verified outcomes are
  the primary candidate signals.
- **Qualification:** A user-authored statement is authoritative evidence of
  what was said or adopted at that time. Its applicability may later be
  narrowed, corrected, superseded, or conflict with other evidence. Preserve
  that history instead of silently converting one statement into permanent
  truth.

### D-003 — Make durable memory scoped, sourced, inspectable, and reversible

- **Date:** 2026-07-15
- **Status:** Confirmed decision
- **Decision:** Durable claims must preserve scope, provenance, confidence,
  time, and revision history. High-impact changes must not happen silently.
- **Basis:** Originating proposal plus the user's explicit agreement with the
  decision-persona framing.

### D-004 — Maintain an exhaustive research record

- **Date:** 2026-07-15
- **Status:** Confirmed decision
- **Decision:** Create a research directory, preserve everything substantive
  from the conversation, document consulted research, and define an AGENTS
  contract so later work does not lose evidence or decisions.

### D-005 — Do not finalize infrastructure before explicit confirmation

- **Date:** 2026-07-15
- **Status:** Confirmed decision
- **Decision:** No infrastructure-related selection may become an AGENTS rule
  or confirmed project decision until the user explicitly approves it.
- **Effect:** Research may state requirements and compare candidates, but it
  must keep them visibly unconfirmed.

### D-006 — Additional suggestions are welcome as research candidates

- **Date:** 2026-07-15
- **Status:** Confirmed decision
- **Decision:** Agents may add useful research directions and warnings, but
  those additions remain candidates until explicitly approved.

### D-007 — Begin with the personality core

- **Date:** 2026-07-15
- **Status:** Confirmed product direction
- **Decision:** The first conceptual target is a strong personality core. The
  broader system should be designed around that core rather than treating
  persona as final-layer prompt decoration.
- **Qualification:** This does not select the representation, schema, model,
  storage, or runtime.

### D-008 — Combine personal memory with external reasoning capability

- **Date:** 2026-07-15
- **Status:** Confirmed behavioral requirement
- **Decision:** The product should use both its durable personal memory and an
  API or agent-LLM reasoning capability when producing help, judgment, or
  conversation.
- **Qualification:** No provider, model, API, or integration is selected. The
  personality core must remain conceptually separable from one reasoning
  provider.

### D-009 — Require local-first operation and adequate security

- **Date:** 2026-07-15
- **Status:** Confirmed requirement
- **Decision:** The system must be able to operate locally and must meet a
  security level appropriate for highly sensitive personal history and derived
  persona artifacts.
- **Qualification:** Containerized operation was suggested as a possibility,
  not approved as the deployment architecture. Security threat modeling and
  measurable acceptance criteria remain open.

### D-010 — Keep the project open source and generally usable

- **Date:** 2026-07-15
- **Status:** Confirmed product direction
- **Decision:** The software should be open source and public rather than a
  private one-off implementation for a single user.
- **Qualification:** Public source does not imply that any person's raw
  history, derived persona, secrets, or private configuration is public. The
  exact license and data boundary remain open.

### D-011 — Treat fabricated reading or memory as a critical failure

- **Date:** 2026-07-15
- **Status:** Confirmed safety requirement
- **Decision:** The system must not claim to have read, remembered, inspected,
  or learned from material for which it has no verifiable source receipt.
- **Effect:** Unknown or unavailable evidence must cause an explicit unknown,
  abstention, or question rather than a fabricated recollection.

### D-012 — Preserve continuity and learn from outcomes

- **Date:** 2026-07-15
- **Status:** Confirmed behavioral requirement
- **Decision:** The product should retain what it last did and tried, connect
  actions to outcomes, derive lessons from mistakes, and improve future
  behavior.
- **Qualification:** Learning means proposing traceable candidate updates. It
  does not override D-003 or authorize silent, irreversible self-modification.
- **Later clarification:** D-018 permits evidence-gated, versioned, reversible
  automatic promotion. Candidate status and change receipts must remain
  inspectable even when per-item approval is not required.

### D-013 — Use temporal holdout as an accepted evaluation method

- **Date:** 2026-07-15
- **Status:** Confirmed evaluation direction
- **Decision:** A chronological holdout in which later user responses and
  outcomes are hidden from the model is acceptable as a persona test.
- **Qualification:** Dataset boundaries, leakage controls, baselines, metrics,
  and pass thresholds remain unconfirmed.

### D-014 — Investigate copilot and cross-conversation communication

- **Date:** 2026-07-15
- **Status:** Confirmed product direction
- **Decision:** The product should be capable of inspecting relevant
  conversations, helping as a copilot, and eventually writing or conversing in
  other conversations.
- **Qualification:** This is a desired capability, not permission to act.
  Read, draft, send, approve, and execute authority must be decided separately.

### D-015 — Treat mission as a dynamic hierarchy

- **Date:** 2026-07-15
- **Status:** Confirmed product direction
- **Decision:** Mission may represent anything the individual is currently
  doing and must therefore be dynamic rather than one fixed global objective.
- **Research interpretation:** Model identity, long-range direction, project,
  task, and immediate action as nested or competing mission levels with
  explicit state, priority, and outcome.

### D-016 — Use one subconscious core and a conscious workspace

- **Date:** 2026-07-15
- **Status:** Confirmed functional direction
- **Decision:** Use one durable personality core analogous to a subconscious,
  together with a conscious layer for current context, goals, reasoning, and
  action.
- **Delegated design choice:** The user delegated selection of the most
  appropriate operating-mode model. The research process adopts explicit
  Mirror, Advisor or Mission, Copilot, Observer or Learner, and Delegate modes
  as the working functional model.
- **Qualification:** This is a testable cognitive metaphor, not a claim of
  sentience and not an infrastructure selection.

### D-017 — Target the full action surface but separate capability from authority

- **Date:** 2026-07-15
- **Status:** Confirmed long-term product direction
- **Decision:** The intended system should eventually be capable of reading,
  inspecting, drafting, sending, starting conversations, operating tools,
  modifying files, and approving other-agent work.
- **Qualification:** Possessing a capability does not grant permission to use
  it. Delegate mode requires explicit, scoped, revocable authority and may not
  be entered through inferred persona confidence.

### D-018 — Make persistence autonomous inside a protected envelope

- **Date:** 2026-07-15
- **Status:** Confirmed behavioral direction
- **Decision:** Event capture, learning, persistence, and improvement should be
  autonomous rather than requiring the user to approve every memory.
- **Guardrail:** Automatic learning must remain sourced, scoped, versioned,
  observable, testable, and reversible. The system may not autonomously expand
  its authority, weaken provenance, export identity, disable revocation, or
  redefine the represented person.
- **Open detail:** Exact evidence and regression thresholds for automatic core
  promotion require research and user-visible acceptance tests.

### D-019 — Keep public code separate from private minds

- **Date:** 2026-07-15
- **Status:** Confirmed privacy requirement
- **Decision:** Project code and general schemas may be public, but a real
  person's raw history, derived identity, and personality core must remain
  inside that person's controlled private boundary and must never be included
  in the public project or uploaded as a reusable identity artifact.
- **Basis:** The user explicitly described exposing another person's identity
  as deeply invasive and unacceptable.
- **Open boundary:** Deliberate outbound messages and the minimal task context
  given to an external reasoner may still reveal personal information. That
  disclosure boundary requires a threat model and explicit rules.

### D-020 — Convert unknowns into reusable sourced memory

- **Date:** 2026-07-15
- **Status:** Confirmed behavioral requirement
- **Decision:** When required information is genuinely unknown, the system
  should ask, learn from the answer, persist it with provenance and scope, and
  use it in a materially similar later context.
- **Qualification:** It must revalidate when time, scope, or later outcomes
  conflict. It must not repeatedly ask for valid known information or invent
  an answer to avoid asking.

### D-021 — Research human-like functional continuity without claiming sentience

- **Date:** 2026-07-15
- **Status:** Confirmed research target
- **Decision:** Investigate persistent identity, autobiographical memory,
  current self-model, active goals, uncertainty awareness, reflection, and
  continuity across restarts as a combined functional target.
- **Qualification:** Here, "consciousness" names the requested functional
  target: continuity, self-model, active goals, reflection, and uncertainty
  awareness. Evaluation is limited to observable functions; subjective
  sentience is outside the project's claim scope.

### D-022 — Generate a combined Markdown context at conversation completion

- **Date:** 2026-07-15
- **Status:** Confirmed documentation requirement
- **Decision:** Provide a repository script that combines every tracked or
  non-ignored untracked Markdown source into one file at the end of substantive
  project-research conversations.
- **Implementation contract:** Sources must be deterministic, path-labeled,
  current-working-tree aware, and included exactly once. The generated output
  must exclude itself and remain outside Git authority.
- **Trigger limitation:** The current enforcement is the research AGENTS
  completion rule or explicit manual execution. No application-level
  conversation hook has been selected or installed.

### D-023 — Treat the first returned reports as inputs, not design authority

- **Date:** 2026-07-15
- **Status:** Confirmed research disposition under delegated judgment
- **Decision:** Preserve the first returned report as an unverified product
  brief and the second as an unverified research map. Prioritize source-auditing
  and testing the second report's hypotheses because it contributes more to the
  cognitive-core research, but do not treat either report as architecture,
  scientific proof, or product authority.
- **Basis:** The user supplied both reports, stated that the second appeared
  substantially stronger, and explicitly delegated the comparative decision to
  Codex.
- **Qualification:** This decision does not approve any named technology,
  protocol, model, storage mechanism, threshold, license, deployment topology,
  product category, or claim in either report.
- **Detailed evidence:**
  [Comparative report review](report-review-2026-07-15.md)

### D-024 — Integrate every research report into a living convergence map

- **Date:** 2026-07-15
- **Status:** Confirmed research-process decision
- **Decision:** During the research phase, preserve each returned report,
  organize its information into the correct dependency order, distinguish
  evidence from inference and prescription, and update a living model of the
  system's required shape. Codex should also guide the user toward the next
  evidence and decisions needed rather than merely summarize reports.
- **Basis:** The user explicitly assigned Codex the ongoing responsibility to
  organize research results, avoid forgetting this duty, move gradually toward
  the appropriate structure, and guide the user in that direction.
- **Qualification:** The convergence map is not architecture authority.
  Report-derived technologies, thresholds, providers, storage, deployment, or
  protocols remain unconfirmed unless separately approved under D-005.
- **Durable implementation:**
  [Research intake rules](AGENTS.md#research-report-intake-and-convergence) and
  [convergence map](convergence-map.md)

### D-025 — Implement a Mirror-first coding-judgment V1

- **Date:** 2026-07-15
- **Status:** Confirmed implementation decision
- **Decision:** The first falsifiable product slice is a local command-line
  scientific harness for coding judgment. Mirror predicts a later user
  decision and required evidence; Advisor may propose useful divergence. The
  long-term mind-like scope remains broader, but it is not the V1 claim.
- **Basis:** The user delegated the detailed plan, reviewed the proposed V1,
  and then explicitly instructed Codex to implement it.
- **Authority boundary:** Mirror and Advisor may read and write private local
  research artifacts. They may not send, execute, automatically promote a
  candidate, present output as user-authored, or claim an external action
  occurred without explicit scoped authority.
- **Scientific qualification:** Implementing the harness does not validate the
  representation. A real user-audited temporal holdout must still beat simple
  baselines.

### D-026 — Freeze the V1 local runtime and storage baseline

- **Date:** 2026-07-15
- **Status:** Confirmed implementation decision
- **Decision:** V1 uses Python 3.12, PostgreSQL 18.4, pgvector 0.8.2, Docker
  Compose, and explicit SQL tables for provenance and dependency edges.
- **Rejected for V1:** A separate graph database, GraphRAG, Graphiti, Mem0,
  fine-tuning, a web UI, and a multi-user service.
- **Change rule:** A later experiment may challenge this baseline, but no new
  framework or storage authority may be added without measured need and a new
  explicit decision.
- **Observed implementation:** The pinned container image built, reported the
  expected PostgreSQL and pgvector versions, and accepted the initial migration
  on loopback.

### D-027 — Enforce a strict-local identity and D0-only egress boundary

- **Date:** 2026-07-15
- **Status:** Confirmed implementation and privacy decision
- **Decision:** Raw corpus, normalized events, declarations, derived identity,
  embeddings, labels, reports, and model outputs remain outside every Git
  worktree. Real-data operations require an explicit outside-Git private root and local
  database storage. External adapters may receive D0 public or explicitly
  synthetic material only; D1 through D5 are blocked.
- **Credential rule:** The project must not inspect or copy ChatGPT, Codex,
  browser, IDE, or provider credential stores.
- **Input rule:** The first real-export operation is metadata-only inventory.
  Ingestion requires an explicit approval bound to the sealed manifest.
- **Attribution rule:** A raw user-role turn identifies the message author, not
  the claim holder of every pasted or quoted span. Until explicit adoption or
  span attribution exists, it remains `user_turn_unattributed` with an unknown
  claim holder and cannot seed represented-user identity.
- **Runtime rule:** Real inputs must resolve outside Git. Their database
  connection must use a non-superuser role that can insert audit receipts but
  cannot update, delete, or truncate the audit ledger. Protected mutations and
  audit receipts commit together.
- **Storage qualification:** Real inputs require an explicit local root outside
  Git. The project makes no host-storage-product claim; identity, authority,
  provenance, egress, and capability controls remain independent.

### D-028 — Support cold start with explicit uncertainty and bootstrap learning

- **Date:** 2026-07-15
- **Status:** Confirmed implementation decision
- **Decision:** The system must remain useful when longitudinal history is
  absent. Mirror abstains and asks one high-value question; Advisor may offer
  generic advice while declaring personal fit unknown. Explicit user-authored
  bootstrap declarations may seed the system but retain declaration authority
  and do not become observed behavior.
- **Learning boundary:** Unknowns may be asked and persisted with source,
  scope, time, and revision lineage. No answer is silently generalized across
  incompatible contexts.

### D-029 — Use local model identifiers as replaceable baselines

- **Date:** 2026-07-15
- **Status:** Confirmed implementation baseline; live behavior unverified
- **Decision:** The provider-neutral local reasoner defaults to
  `openai/gpt-oss-20b` and the embedding adapter defaults to `BAAI/bge-m3`.
  Both accept loopback endpoints only and neither owns the cognitive core.
- **Trust rule:** Loopback describes transport location, not provider location.
  D1 through D5 remain blocked unless the operator separately attests that the
  endpoint cannot proxy or forward requests to another machine or provider.
  The client refuses redirects and bounds adapter request and response size.
- **Qualification:** No weights were downloaded and no live endpoint was run.
  The identifiers are testable defaults, not a claim that either model is best
  for the user or corpus.
- **Deferred:** An account-based Codex adapter remains unsupported until an
  official, project-safe isolation boundary is demonstrated. Token or session
  scraping is prohibited.

### D-030 — Use AGPL-3.0-only for the V1 repository

- **Date:** 2026-07-15
- **Status:** Confirmed implementation decision
- **Decision:** The package metadata and existing repository license use
  AGPL-3.0-only for V1.
- **Qualification:** This does not settle future contributor governance,
  trademark, hosted-service, or commercial distribution policy.

### D-031 — Prohibit god objects and enforce source-size limits

- **Date:** 2026-07-15
- **Status:** Confirmed engineering decision
- **Decision:** Production and test code must be divided by clear
  responsibility with explicit dependencies. A hand-written Python or SQL file
  may contain at most 300 physical lines, a function or method at most 50
  source lines, and a class at most 200 source lines.
- **Basis:** The user explicitly prohibited god objects, requested an enforced
  maximum rather than unbounded files, and required pytest and ordinary code
  quality rules.
- **Enforcement:** The limits are recorded in the root `AGENTS.md` and checked
  by `scripts/check-source-limits.py` as part of pytest and handoff validation.
- **Exception rule:** An exception requires a prior written architecture
  decision. Convenience is not sufficient.

### D-032 — Start with a data-free manager before feeding persona memory

- **Date:** 2026-07-15
- **Status:** Confirmed implementation direction
- **Decision:** The next slice starts as a small manager that remains useful
  without conversation history. Personal history can be supplied later rather
  than being a startup dependency.
- **Basis:** The user explicitly proposed running the first manager without
  data, feeding memory afterward, and auto-generating its initial memory.
- **Implementation interpretation (assistant-derived):** The current
  auto-generated initial memory is an
  ephemeral D0 system operating seed. It contains protected working rules,
  reports zero persona evidence, and cannot be retrieved or promoted as a
  represented-user claim. This is a reversible design choice under delegated
  technical authority, not a user fact or the only possible cold-start design.
  It follows D-002, D-011, D-027, and D-028; no personal fact can be generated
  from absence of evidence.
- **Open continuation:** The first interaction-to-persona-candidate protocol,
  persistence trigger, confirmation rule, and later reuse test remain open.
  The current slice writes nothing and performs no action.

### D-033 — Preview explicit declarations before creating durable persona memory

- **Date:** 2026-07-15
- **Status:** Confirmed implementation direction
- **Decision:** The first visible persona surface is a non-persisting preview
  built only from explicitly adopted user declarations. It may organize those
  declarations into the candidate four-view ontology and scoped objects, but
  it may not generate a personality summary, infer missing traits, generalize
  across scope, call a provider, write a database, or promote a core record.
- **Basis:** The user asked to continue, run the tests, create a persona to
  inspect, and judge progress against the research. D-002, D-011, D-019,
  D-028, and D-032 require the first result to mark missing evidence explicitly
  and keep unverified personal fields unknown.
- **Attribution rule:** Every real preview item must explicitly declare user
  authorship, represented-user claim ownership, adoption, source authority,
  and the identity-interpretation plane. Arbitrary Markdown, assistant text,
  third-party text, and system controls cannot silently enter this path.
- **Privacy rule:** Real D3 source files must remain inside the protected
  private root and outside Git. The preview stays in process/stdout and is not
  an authorization or persistence receipt.
- **Persistence qualification:** The current bootstrap schema cannot retain
  all adoption metadata. Real bootstrap and replacement writes are blocked
  until an explicitly approved, provenance-preserving schema or linked receipt
  passes a storage round-trip; synthetic D0 writes remain test-only apparatus.
- **Scientific qualification:** This is declared-profile apparatus, not
  behaviorally or temporally validated persona evidence. The user must be able
  to correct it before any durable-candidate protocol is considered.

### D-034 — Isolate synthetic and private identity planes by subject

- **Date:** 2026-07-15
- **Status:** Confirmed implementation safety boundary
- **Decision:** One represented subject cannot contain both D0 synthetic
  identity fixtures and non-D0 private identity records. Repository mutations
  serialize on the subject, reject cross-plane inserts before any audit or data
  write, and require corrections to remain in the target record's data class.
- **Basis:** D-019 and D-027 prohibit public or synthetic material from being
  mistaken for private identity. A synthetic fixture beside a legacy D3 record
  could otherwise influence retrieval or supersede the real record while still
  passing the D0 egress policy.
- **Legacy rule:** Synthetic inference rejects subjects containing non-D0
  evidence. Real inference rejects D0-contaminated subjects and stored D3
  declarations whose adoption provenance cannot be verified. D3 targets remain
  invalidation-only until D-033's persistence qualification is resolved.
- **API and contention rule:** Every public inference reader requires an
  explicit D0 or D3 plane and repeats the readiness check inside its read
  methods. Plane-filtered inspection uses different method names and cannot
  satisfy the inference protocol. Subject lock contention fails immediately
  with retryable `identity_subject_busy`; it must not wait in an advisory-lock
  cycle.
- **Qualification:** This is a contamination boundary, not evidence that the
  stored persona is correct. It does not select a durable schema, namespace, or
  database topology for real use.

### D-035 — Delegate ordinary technical and research decisions while retaining identity authority

- **Date:** 2026-07-15
- **Status:** Confirmed project-governance decision
- **Decision:** Codex may autonomously choose research and implementation
  sequencing, reversible local experiments, architecture recommendations,
  scoped implementation details, test design, and evidence-based rejection or
  refinement without asking for approval at every ordinary step.
- **Retained authority:** The represented user remains the canonical authority
  for whether a persona represents them, access to private corpus or third-party
  data, external egress or actions, destructive changes, material cost, merge,
  deployment, release, and every repository ask-first boundary.
- **Attribution boundary:** Delegation does not turn assistant inference or
  assistant-normalized prose into represented-user identity evidence. It does
  not approve automatic persona promotion or relax correction, provenance,
  privacy, and abstention requirements.
- **Infrastructure boundary:** D-005 and repository ask-first rules still apply
  to material dependency, schema, configuration, persistence, and security-
  boundary changes. Where those rules require explicit approval, Codex may
  recommend but may not silently implement the change.
- **Scientific rule:** A measured failure may reject the current architecture.
  Delegated decision authority is a workflow rule, not evidence that the
  representation is valid or faithful.

### D-036 — Require atomic interaction review before persona promotion

- **Date:** 2026-07-15
- **Status:** Confirmed implementation decision
- **Decision:** Before a current-session response can become persona memory, a
  provisional interaction receipt may project it into multiple atomic,
  span-linked proposals. Speech act, modality, claim type, target layer,
  literal normalization, inference, candidate consequence, attribution,
  classification confidence, applicability confidence, and explicit null
  reasons remain separate review fields.
- **Authority rule:** Source authorship does not confirm the interpretation.
  Every atomic result remains `proposed`, requires represented-user correction,
  has `core_eligible=false`, and cannot persist, grant authority, perform an
  action, or promote itself.
- **Layer rule:** Project constitution, protected controls, architecture
  candidates, scoped policy, mission state, episodic memory, experiment
  backlog, research vision, and persona candidates remain distinct targets.
  A protected instruction may also motivate a separate persona hypothesis, but
  the latter stays an inference until independently supported.
- **Temporal rule:** The original modality is immutable evidence. A later
  confirmation creates later lifecycle evidence; it does not rewrite an
  earlier question or proposal. Confirmed cold-start and hard source-size
  decisions therefore remain active without falsifying their exploratory or
  delegated source wording.
- **Comment disposition:** The supplied combined record is retained as a
  requirements checklist rather than adopted verbatim as a storage schema.
  Existing owners for source, claim, identity, continuity, correction, and
  promotion remain separate unless later evidence supports consolidation.
- **Implementation boundary:** This checkpoint is a typed, in-process review
  projection with synthetic unit evidence. It adds no migration, dependency,
  database write, provider, extractor, retrieval framework, or remote action.

### D-037 — Prove the decision lifecycle before model integration

- **Date:** 2026-07-15
- **Status:** Confirmed implementation decision
- **Decision:** A source-linked atomic proposal becomes active only through an
  explicit per-atom represented-user decision. The supported actions are
  `confirm`, `reject`, `split`, `narrow_scope`, `mark_temporary`,
  `make_project_rule`, `reject_inference`, and `propose_for_core`. Wildcards
  are forbidden. One receipt may carry several project decisions, but every
  atom keeps an independent decision object and persona candidates require
  explicit per-atom treatment.
- **Lifecycle rule:** The original review and proposals remain immutable.
  Corrections are new canonical SHA-256 receipts linked to the review and
  predecessor receipt. Partial replies leave untouched atoms pending. A later
  decision for the same atom records explicit supersession without deleting
  its earlier event.
- **Replay rule:** Replay preserves supplied order and fails closed on missing,
  duplicate, reordered, malformed, hash-mismatched, cross-subject,
  cross-review, cross-class, unknown-atom, or semantically invalid correction
  input. Fixed typed inputs produce the same state digest. A deletion request
  currently returns only the complete dependency projection; it performs no
  deletion.
- **Resolution rule:** Explicit supersession and applicability by person,
  project, role, audience, risk, and time are evaluated before target-layer
  partitioning. Protected controls, project rules, mission state, episodic
  context, persona candidates, and research candidates cannot leak into one
  another. Conflicting applicable decisions remain visible and force
  abstention; recency and repetition do not select a winner.
- **Core boundary:** `propose_for_core` requests a later evaluation only.
  Persona confirmation never changes `core_eligible=false`, and project rules
  never become persona evidence.
- **Implementation boundary:** V1.2 remains a typed, in-process, synthetic
  lifecycle. It adds no database schema, migration, persistence, retrieval,
  extractor, model, provider call, external access, or action authority.
- **Held item:** The private local candidate identified by the opaque label
  **3B** remains pending. Recording that workflow state does not confirm its
  content, correctness, stability, or eligibility for a core.
- **Scientific qualification:** This proves deterministic protocol behavior,
  not persona fidelity. Real correction burden, semantic conflict detection,
  annotation agreement, durable round-trip, deletion, and predictive value
  remain untested.

### D-038 — Permit one pinned local extractor as a proposal-only experiment

- **Date:** 2026-07-15
- **Status:** Confirmed bounded implementation decision
- **User authorization:** The user authorized installation and fast local
  testing with a capable roughly 7B-class model, explicitly suggesting Ollama
  or an already available Harness surface. This replaces D-037's temporary
  model-download stop only for this local, proposal-only experiment.
- **Selected experiment:** The inspected shell exposed neither Ollama nor a
  Harness executable. The bounded path therefore uses `llama-server` build
  9803 with official Qwen3-8B Q4_K_M revision
  `7c41481f57cb95916b40956ab2f0b139b296d974` and artifact SHA-256
  `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.
  This is a reproducible experiment pin, not a permanent model winner or a new
  product dependency.
- **Provider boundary:** The server binds only `127.0.0.1`, disables logging
  and its web UI, uses a local acceleration backend, and is identified by a
  fixed alias, revision, and artifact digest. A loopback endpoint still
  requires explicit provider-local attestation before the extractor calls it.
- **Authority boundary:** The model can return only bounded atomic proposals.
  Deterministic code re-resolves exact source spans, inherits source scope,
  rejects invalid or duplicate structures, and leaves every proposal pending,
  confirmation-required, core-ineligible, non-persisted, and without action
  authority. Correction, replay, supersession, and conflict resolution remain
  model-free.
- **Privacy boundary:** The local synthetic smoke test used D0 text only. Real
  current-thread identity text was not processed at this checkpoint. A later
  user authorization established a bounded outside-Git review path. No corpus,
  metadata inventory, database migration, or external provider was added.
- **Scientific qualification:** One synthetic two-atom smoke test establishes
  protocol compatibility and practical latency for one local run only. It does
  not measure extraction precision, correction burden, persona fidelity, or
  whether 8B is preferable to a 1–3B extractor.

### D-039 — Use an explicit outside-Git root for the first private review

- **Date:** 2026-07-15
- **Status:** Superseded by D-042
- **Historical decision:** The user authorized a bounded local review pilot
  while requiring its source and result to remain under one explicit
  outside-Git private root.
- **Non-expansion rule:** The exception cannot be reused by corpus inventory,
  database access, durable persona storage, synthetic mode, or any path inside
  Git. It grants no model authority, identity truth, promotion, persistence,
  action, external egress, or deletion permission.
- **Observed result:** A fresh current-thread interaction produced ten
  proposal-only atoms through the pinned local extractor. The first attempt
  failed closed because generated source text did not resolve exactly and
  wrote no review. The corrected contract restricts the model to deterministic
  exact source segments; the second attempt succeeded while leaving all ten
  atoms pending and core-ineligible.
- **Scientific qualification:** Manual inspection found an interpretation that
  extended beyond its cited source text and required correction. The run is
  therefore useful extraction and correction-burden evidence, not persona
  evidence. No correction receipt exists until the user chooses an explicit
  action for one or more atoms.

### D-040 — Record the user-reviewed first bounded correction batch

- **Date:** 2026-07-15
- **Status:** Retained after explicit user ratification; initial execution-order
  violation recorded
- **Authorization chronology:** The first bounded batch was applied before the
  required user approval. The user then explicitly approved A1-A5 and chose to
  keep the result. This is post-hoc ratification, not evidence that the initial
  application was authorized. The later ratification supports retaining the
  bounded outcomes from that point forward; it does not rewrite the earlier
  execution as pre-authorized.
- **Private disposition:** The exact source text, proposal cardinality, atom identifiers,
  replacement interpretations, rejection reasons, receipt identifiers,
  digests, and paths remain outside Git. The public record retains only the
  categorical result that the bounded review remained partial.
- **Authority boundary:** The correction receipt records the represented user
  as actor and claim holder with explicit adoption. It grants no action
  authority, creates no durable persona, performs no database write or
  deletion, and does not promote any core candidate.
- **Replay result:** The first private receipt replayed deterministically to
  the same partially reviewed state. The dependency projection remains a plan
  only; its cardinality stays private and deletion was not performed.
- **Scientific qualification:** This is the first genuine correction-loop
  observation and proves that the user can reject and restructure model
  proposals through the typed protocol. It does not establish extractor
  accuracy, persona fidelity, temporal stability, or persistence quality.

### D-041 — Complete the user-reviewed bounded correction chain

- **Date:** 2026-07-15
- **Status:** Confirmed represented-user correction decision
- **User authorization:** After the remaining bounded recommendations were shown,
  the user explicitly instructed the system to apply them. The authorization
  covered those bounded atom actions, not a wildcard persona update.
- **Private disposition:** A later receipt was appended to its predecessor.
  The selected bounded review reached a complete active state. Exact proposal
  counts, outcome distributions, content, and mappings remain outside Git.
- **Authority boundary:** The second receipt is an explicit D3 represented-user
  correction with no database or provider call, persistence, action authority,
  deletion, or automatic core promotion. Candidate interpretations remain
  scoped and non-authoritative.
- **Replay result:** Independent full-chain replays produced the same complete
  reviewed state. The earlier receipt remains intact; the later receipt
  targeted previously pending atoms, so no earlier decision required
  supersession. The dependency-only deletion projection was not executed, and
  its cardinality remains private.
- **Scientific qualification:** This closes one selected correction form, not
  the extractor-quality question. The sample is small, ordered, and drawn from
  one interaction; it does not establish annotation agreement, persona
  fidelity, temporal stability, durable memory, or safe erasure.

### D-042 — Make the explicit outside-Git root the complete local path gate

- **Date:** 2026-07-16
- **Status:** Confirmed user decision and implemented policy
- **Decision:** The project will not inspect or certify the host's
  storage-at-rest product. Real inputs and generated private artifacts must use
  an explicitly selected local root outside every Git worktree.
- **Preserved controls:** Source containment, Git exclusion, content-free
  public records, provenance, no-egress defaults, restricted database roles,
  and separate loopback-model locality attestation remain independent gates.
- **Removed controls:** Platform-specific storage probes, attestation state,
  environment variables, CLI flags, exception markers, and override branches
  are not part of the project contract.
- **Scope boundary:** This decision changes only project-owned
  storage-product verification. Existing identity-evidence, persona-promotion,
  persistence, action, egress, and deletion-authority rules remain unchanged.

### D-043 — Authorize a content-free local Codex metadata inventory

- **Date:** 2026-07-16
- **Status:** Confirmed user authorization and completed private operation
- **Decision:** Inspect only canonical local Codex session metadata, create the
  resulting manifest outside Git, and keep all personal, machine, session, and
  manifest details out of the public repository.
- **Observed result:** One private inventory completed and its checksum was
  verified. It copied no content fields, derived no claim, and called neither a
  database nor a model provider.
- **Private disposition:** Actual roots, file locators, identifiers, dates,
  sizes, counts, opaque keys, checksums, and manifest content remain private.
- **Limits:** This is not an official account export, content ingestion,
  annotation result, persona evidence, deletion proof, or model benchmark. The
  checksum is not an authenticity signature, and concurrent path replacement
  by another process running under the same OS account remains outside the
  current threat model.
- **Repository qualification:** Current-tree redaction does not remove details
  already present in older public Git history. D-045 records the separate
  decision and publication boundary for replacing that feature history.

### D-044 — Require neutral and accountable public research language

- **Date:** 2026-07-16
- **Status:** Confirmed user correction and documentation policy
- **Decision:** Public research records must describe user decisions,
  deferrals, corrections, uncertainty, and open questions without judging the
  user's competence, motives, or risk posture.
- **Attribution rule:** Failed interpretations and procedure errors must name
  the responsible model, protocol, assistant, or implementation. Scientific
  negative evidence remains visible, but it must not be reframed as a user
  deficiency.
- **Historical correction:** D-001 now retains persona imitation in the
  product direction while measuring judgment fidelity first. D-040 now records
  that the first A1-A5 batch was executed before approval and retained only
  after the user's later ratification.

### D-045 — Replace the feature branch with a privacy-clean public snapshot

- **Date:** 2026-07-16
- **Status:** Confirmed user authorization; implemented by this snapshot
- **Decision:** Replace the public `codex/v1-scientific-core` feature history
  with one validated snapshot commit based on the existing public `main`
  branch. Keep a rollback ref locally and do not publish it.
- **Reason:** Earlier feature commits contain public-history details that are
  absent from the current tree. A snapshot removes that feature chain from the
  live branch while preserving a common base for the open pull request.
- **Publication rule:** Update only the named branch with an exact
  `--force-with-lease`, verify the pull-request head and merge ref afterward,
  and leave `main` unchanged.
- **Limit:** Ref replacement does not prove physical deletion from hosting
  caches or unreachable-object retention. Stronger platform-side purging is a
  separate repository-level action.

### D-046 — Authorize an ephemeral local Codex content parser pilot

- **Date:** 2026-07-16
- **Status:** Confirmed user authorization and completed private operation
- **Decision:** Return to the explicitly selected private local Codex history
  through one bounded, memory-only parser feasibility pilot. The operation may
  read canonical `sessions` and `archived_sessions` content but must emit and
  persist no message text or normalized event.
- **Source-authority rule:** Structural `user` turns remain
  `user_turn_unattributed` with an unknown claim holder. Assistant text remains
  assistant context. Developer, system, reasoning, tool, attachment, image,
  and binary material cannot become dialogue or persona evidence in this
  checkpoint.
- **Transient governance:** The user reported the selected local history as
  their corpus. Possible quotations, pasted text, and third-party material
  remain unresolved D2 source content and cannot be interpreted or promoted.
  Derived events exist only in process memory and are discarded at exit; the
  source files are read-only and unchanged.
- **Observed result:** The bounded real parser completed twice with matching
  content-free snapshot and count summaries. The private output-root file
  count remained unchanged. No content was emitted or persisted, no claim or
  annotation was created, and no database or model provider was called.
- **Privacy disposition:** Actual content, paths, filenames, identifiers,
  dates, counts, hashes, and private summaries remain outside Git.
- **Review hardening:** Independent privacy review found that unexpected JSON
  discriminator strings could become count-summary keys. Record, payload, and
  content-part types are now reduced to fixed allowlisted categories, with a
  sentinel regression test proving that raw discriminator text is not emitted.
- **Next stop:** Durable evidence windows require a separately approved
  ownership and third-party exclusion rule, retention period, deletion
  lineage, and private artifact contract. Bulk processing, ingestion,
  annotation, model use, persona construction, and automatic promotion remain
  unauthorized by this checkpoint.
- **Scientific qualification:** This establishes parser feasibility and
  deterministic bounded replay only. It does not establish corpus quality,
  annotation agreement, persona fidelity, deletion propagation, model
  quality, or full-corpus readiness.

### D-047 — Treat the first real 24+8 pack as annotation feasibility only

- **Status:** Implemented and bounded.
- **Decision:** The 24 unique windows and eight blind repeats are an
  annotation-feasibility pack. Its bounded chronological partitions are named
  annotation-development and annotation-reserved; neither partition is a
  protected persona-quality holdout.
- **Evidence:** A bounded real run independently reloaded its selected source
  files, reproduced the same receipts, retained structural user turns as
  unattributed, separated annotator and evaluator roots, and passed a
  disposable derived-deletion canary. Public output contains only aggregate
  counts and capability limits.
- **Retention:** Private artifacts and deletion tombstones have a seven-day
  expiry, enforced on store-backed study access. No background deletion
  guarantee is claimed. Corrupt or linked storage is surfaced as an incomplete
  purge instead of being skipped.
- **Consequence:** No persona score, baseline win, model comparison, or core
  promotion may be reported from this pack. The represented user must first
  label and adjudicate it; a separate protected chronological Mirror set must
  then be frozen before predictors run.
- **Limit:** Separate private directories provide operational blinding only,
  not cryptographic isolation or an authorization boundary. The deletion
  receipt covers a disposable canary, not the unchanged source corpus.

### D-048 — Freeze a distinct metadata-only session-start-ordered Mirror holdout

- **Status:** Implemented and verified in the active replacement private pack.
- **Decision:** Reserve eight to twelve later-by-canonical-filename-session-start,
  explicit-lineage-disjoint source files before selecting the 24 earlier
  annotation files. Read only the bounded first session-metadata record while
  frozen; dialogue content, target labels, and predictor access remain false
  until annotation labels are sealed.
- **Evidence:** The bounded replacement run passed the configured minimum
  later-by-session-start holdout shape, found no explicit lineage overlap, and used no model or
  database. It emitted no private content publicly. The prior pack was deleted
  only after its 32 labels were verified empty and a staging replacement passed;
  the staging copy was deleted after promotion. Only the promoted private run remains.
- **Evaluation consequence:** Six target-isolated deterministic baselines now
  have synthetic mock/support coverage with provenance and abstention metrics.
  Real baseline predictions cannot run until represented-user annotation labels
  are complete and exact duplication is checked when the holdout is opened.
- **Limit:** Canonical filename session-start order is not proof of event-time
  order, active branch membership, ownership, semantic independence, or persona
  relevance. Exact content overlap remains unknown while dialogue stays sealed.
  The label completion marker is local operator attestation, not cryptographic
  identity authentication. No real persona-quality claim or acceptance
  threshold follows from this freeze.

### D-049 — Preserve initial labels and separate repeat adjudication

- **Status:** Implemented; represented-user submission remains pending.
- **Decision:** The first complete 32-label submission and its raw eight-pair
  agreement receipt become immutable regardless of mismatch. Only mismatched
  pairs enter a separate adjudication artifact linked to that initial receipt.
- **Integrity rule:** Context digests are recomputed from their exact supplied
  text. The final receipt binds the resolved sealed labels and, when present,
  the completed adjudication set. Adjudication cannot rewrite the initial
  judgments or create automatic persona promotion. Exclusive-create writes,
  a per-study transaction lock, and index-to-disk inventory checks make
  interrupted or concurrent mutation fail closed instead of overwriting.
  Post-index verification failure restores the prior mutable index before new
  payload cleanup. If index rollback itself fails, committed payloads are
  retained and the operation reports incomplete rollback rather than deleting
  data under the committed index.
- **Retention and deletion:** Every store-backed access performs the on-access
  expiry check. Deletion tombstones expire after seven days, and absence checks
  cover control, annotator, and evaluator roots including unindexed remnants.
  Purge success requires both a matching pre-delete inventory and post-delete
  absence.
- **Public evidence rule:** Corpus-dependent runtime counts remain private.
  Public research may state protocol-fixed cardinalities and categorical
  pass/fail results only.
- **Limit:** This is evaluation-apparatus integrity, not annotation agreement,
  identity authentication, persona quality, or permission to open holdout
  dialogue.

### D-050 — Replace full manual pre-labeling with bounded model-assisted review

- **Status:** Confirmed and implemented as a proposal-only experiment;
  represented-user review remains pending.
- **Decision:** The system should derive provisional persona labels from the
  bounded private data instead of requiring every ordinary user to author a
  complete machine-readable label set from scratch. A small local model may
  propose, but it cannot supply represented-user authority, ground truth,
  persona promotion, or action authority.
- **Hallucination controls:** Use two independent passes, a strict schema with
  only independent fields, deterministic dependent-field materialization,
  exact focus binding, blind-repeat comparison, explicit abstention, a fixed
  audit sample, and a hard review-burden cap. Oversized focus text is guarded
  as unknown and persona-excluded rather than truncated and described as fully
  read.
- **Retry rule:** Preserve an unreliable primary attempt. Permit at most one
  explicitly requested retry linked to the primary receipt; never overwrite
  either attempt. A review draft exists only if the retry remains within the
  configured burden cap.
- **Model status:** The already pinned Qwen3-8B Q4_K_M artifact is an
  experimental local proposer because no available 3B artifact was found. It
  is not a permanent model selection and no download was authorized. The
  provider tuple is explicitly configured and operator-attested; this is not
  runtime cryptographic verification of the serving process.
- **Limit:** Model-assisted review does not replace the full 24+8 gold-label
  protocol or establish persona quality. Holdout dialogue, scoring, durable
  persona memory, and automatic promotion remain closed.

### D-051 — Make assisted proposal review compact, resumable, and receipt-bound

- **Status:** Implemented; represented-user decisions remain pending.
- **Decision:** The represented user may record an assisted audit with card
  numbers and the three bounded actions `confirm`, `correct`, and `not_mine`
  instead of editing the whole machine-readable draft. Partial submissions are
  resumable. Repeating the same action is idempotent; conflicting, duplicate,
  unavailable, or non-selected actions fail before mutation.
- **Correction boundary:** `correct` marks the target but cannot invent the
  replacement judgment. Submission remains blocked until the private draft
  contains an exact, schema-valid represented-user correction.
- **Seal and replay:** A complete audit atomically seals the completed draft,
  exact decisions, and a canonical receipt. Source/proposal ancestry, exact
  spans, immutable hashes, data class, and the selected attempt are rechecked.
  A repeated submission replays the same sealed receipt.
- **Privacy and authority:** Real review decisions and exact text stay outside
  Git. Aggregate CLI output exposes no content or study identifier. A
  represented-user review remains local operator attestation, not
  cryptographic identity, a gold label set, persona-quality evidence, holdout
  authority, or automatic core promotion.
- **Transaction rule:** Draft replacement, immutable artifacts, and index
  update form one rollback-aware transaction under the per-study lock. An
  injected write failure restores the original draft byte for byte; concurrent
  ownership fails closed.

### D-052 — Close the first Gate 0 implementation defects before activation

- **Status:** Implemented checkpoint; receipt-bound storage admission and real
  corpus activation remain blocked.
- **Decision:** Mirror inference must ignore proposed, non-represented-user, or
  empty-provenance candidates; enforce candidate and scope validity windows;
  abstain on conflicting explicit decision markers; and preserve typed labels
  in reasoner evidence.
- **Protocol:** Benchmark freezing rejects interleaved event times, semantic
  manifest tampering, incomplete partitions, and explicit fatal challenge tags.
  Erasure covers both continuity endpoints. Private deletion stages files and
  restores the index on failure. Runtime grants are explicit and protected
  table ownership is rejected. Compact review accepts a private correction
  file, and a local proposer checks the serving response model identity.
- **Evidence:** Synthetic and private-path regression tests plus all 22
  PostgreSQL integration tests against the disposable loopback `ynoy_test`
  database. No real-corpus benchmark result, automatic promotion, external
  egress, or merge is authorized by this checkpoint.
- **Superseded gap:** D-054 replaces the dormant `ClaimCandidate` inference
  path with a receipt-bound canonical claim path. Real-corpus evidence remains
  uncollected.

### D-053 — Maintain a falsifiable mathematical system contract

- **Date:** 2026-07-17
- **Status:** Confirmed documentation and research-process decision
- **Decision:** Maintain a technology-neutral mathematical foundation that
  distinguishes hard safety invariants, candidate models, measurable
  quantities, and evaluation definitions. Use it to expose assumptions and
  design falsification tests, not to imply that an equation proves persona
  quality.
- **Privacy consequence:** Public research may record categorical protocol
  outcomes but not exact private proposal counts, decision distributions,
  dependency cardinalities, host locators, or private artifact fingerprints.
- **Non-decision:** This does not select a graph database, factor-graph runtime,
  retrieval system, model family, learned weights, abstention threshold, or
  utility scalarization.
- **History boundary:** Current-tree redaction is authorized by this decision.
  Replacing already published Git history remains a separate ask-first action.

### D-054 — Use one receipt-bound canonical claim path for inference

- **Date:** 2026-07-17
- **Status:** Implemented synthetic and loopback-PostgreSQL checkpoint
- **Decision:** Mirror and persona preview may read only active
  `CanonicalClaim` records whose represented-user ownership, explicit user
  adoption receipt, exact source links, data plane, scope, validity window,
  and lifecycle bindings validate. Legacy claim and declaration tables remain
  proposal or inspection history and cannot satisfy the inference reader.
- **Layer boundary:** Project constitution, protected control, mission,
  scoped-policy, and persona layers remain distinct. Persona projection uses
  five explicit strata, and conflicts abstain instead of using recency or
  repetition.
- **Erasure:** A source-linked synthetic claim was admitted, retrieved,
  superseded, and erased through PostgreSQL dependency closure. Missing source
  links, future or expired scope, and superseded state fail closed.
- **Authority:** Admission grants no action authority and never performs
  automatic core promotion. This checkpoint does not validate a real persona.
- **Remaining gap:** Lossless corpus vaulting, real annotation, model
  comparison, target-isolated holdout, and real-user quality evidence remain
  open.

### D-055 — Harden the mathematical safety contract before runtime changes

- **Date:** 2026-07-17
- **Status:** Confirmed research and documentation decision
- **Decision:** Define applicability as query-environment membership; separate
  explicit policy, inferred persona, generic advice, and abstention; use
  three-valued same-key conflict; bind adoption to a separate trusted channel;
  require expected-head idempotent review append, complete observer-indexed
  egress traces, registry-complete tombstone-fenced erasure, and persona
  comparison at matched coverage.
- **Trust boundary:** The operating-system user and separate approval channel
  are trusted in V1. Models, reasoners, extractors, and ordinary runtime code
  cannot author verified adoption. A hash proves integrity only. Administrator
  or root compromise remains outside the V1 guarantee.
- **Privacy boundary:** D2-D3 identity data cannot enter model parameters until
  a separate unlearning proof exists. Public records contain no real corpus or
  behavioral aggregate from this work.
- **Non-decision:** No authenticator, threshold, sample minimum, interval
  level, migration, dependency, storage mechanism, or runtime owner is
  selected. No source or test implementation is authorized by this decision.

### D-056 — Apply only verified corrections from the formula-and-flow audit

- **Date:** 2026-07-17
- **Status:** Confirmed research and documentation decision; no runtime change
- **User direction:** After reviewing the report's strengths and defects, the
  user delegated the evidence-filtered next step to the assistant.
- **Decision:** Preserve the supplied report with `Authority: none`; accept only
  findings independently supported by the current contract or primary sources;
  and record rejected prescriptions explicitly. Strengthen D-055 without
  rewriting its historical record.
- **Formal correction:** Derive the same-key unresolved conflict set from a
  deterministic dependency manifest; separate ranking and calibrated persona-
  emission thresholds; enforce authorization independence across its upstream
  projection; prohibit direct or derivative D1-D5 influence on model-parameter
  updates in V1; and require a frozen single-primary or familywise overall
  coverage rule plus absolute per-stratum safety ceilings that cannot hide
  supported high-risk strata.
- **Rejected prescriptions:** Do not convert the narrative `resolve` notation
  into the report's score; do not use its reverse-implication authority rule;
  do not add execution, delegation, budget leases, cryptographic infrastructure,
  or content-bearing provenance snapshots to V1.7.
- **Privacy consequence:** Credentials and third-party personal data gain no
  training path. Erasure tombstones remain non-content-bearing and may not keep
  reversible content-derived values.
- **Non-decision:** Numeric thresholds, kappa choice for a final label design,
  one primary coverage versus a familywise rule, per-stratum ceiling values,
  authenticator, timing threat semantics, runtime owners, dependencies, storage,
  and future execution remain open or separately gated.

### D-057 — Close deterministic formal-contract bindings before implementation

- **Date:** 2026-07-17
- **Status:** Confirmed research and documentation decision; no runtime change
- **User direction:** After reviewing the formal findings, the user explicitly
  requested that the corrections be applied.
- **Decision:** Canonical claims must bind stable claim/subject identity and a
  reviewed subject/layer/decision key. Conflict applies only to distinct active
  same-key claims, and supersession is effective only through a verified,
  query-applicable same-key successor.
- **Evaluation decision:** Persona calibration is exact-target, frozen-profile,
  version/domain-bound, and isolated from sealed outcomes. Matched coverage uses
  a frozen label-blind selector plus case, baseline, cluster, support, and
  inference manifests; sealed results cannot choose or mutate them.
- **State and authority decision:** Review append requires trusted context bound
  to actor, subject, review, stream, event policy, and required adoption.
  Persona/model state may neither select nor alter an authorization tuple.
  Erasure requires a current bound producer-universe attestation, verified
  receipt, future-trace independence, and tombstone fence.
- **Output decision:** Internal Mirror candidates and public tagged judgments
  are disjoint. Only the deterministic basis resolver may emit a public value.
- **Non-decision:** No numeric value, calibration mapping, baseline identity,
  cluster mapping, authenticator, attestation technology, storage/recovery
  boundary, runtime owner, source/test implementation, schema, dependency,
  corpus, model, provider, action capability, commit, or push is selected.

### D-058 — Implement the V1.8 formal runtime contract

- **Date:** 2026-07-18
- **Status:** Implemented deterministic and synthetic runtime checkpoint
- **User direction:** The user explicitly approved the V1.8 plan, including
  completing the existing corpus/vault package, integrating the reviewed
  mathematical research, implementing all 40 mandatory contract tests, and
  publishing green checkpoints to the existing feature branch and draft pull
  request without merging.
- **Decision:** Move the reviewed scope, identity, conflict, supersession,
  judgment-basis, adoption, append, authorization, egress, erasure,
  parameter-isolation, calibration, and matched-coverage contracts into
  deterministic runtime owners. Models remain proposal or ranking producers
  and cannot select basis, adoption, authorization, promotion, or action.
- **Implemented safety boundary:** Private adoption fails closed without a real
  authenticator; the append proof is in-memory only; V1 private state produces
  no external call trace; erasure reports only local or partial results with
  `universal_success=false`; D1–D5 cannot influence parameter updates; and
  numeric comparison values are required frozen inputs rather than defaults.
- **Observed validation:** All 40 mandatory test names are present. The final
  runtime checkpoint passed 498 tests with one qualified skip and 85.46 percent
  branch coverage, plus lint, formatting, strict typing, compilation, source
  limits, and whitespace checks. PostgreSQL integration used only the
  disposable loopback test database.
- **Privacy consequence:** No new real corpus, private fixture, personal
  database migration, model/provider call, credential, machine locator, or
  identity-bearing aggregate was added to Git.
- **Non-decision:** No real authenticator, persistent append store,
  cross-restart tombstone fence, independent producer attestor, backup boundary,
  unlearning method, timing-observer guarantee, baseline winner, calibration
  mapping, numeric threshold, automatic promotion, action capability, merge,
  or persona-quality claim is selected or established.
- **Durable record:** [V1.8 formal runtime conformance record](v1-8-runtime-record-2026-07-18.md)

### D-059 — Resume real corpus work through bounded private checkpoints

- **Date:** 2026-07-18
- **Status:** Confirmed and first bounded checkpoint implemented
- **User direction:** Begin processing the large local history and produce
  tangible persona material, while requiring software-controlled streaming and
  low memory use because the machine is operated remotely.
- **Decision:** Start with the existing 16 MiB ephemeral parser and 32 MiB
  private study-preparation limits. Use only explicit outside-Git roots, one
  local model process, reduced context, sequential proposal calls, deterministic
  rejection gates, and cleanup after every model run. Do not snapshot or load
  the complete corpus as the first step.
- **Observed result:** A conservative opaque-parent lineage repair enabled the
  bounded private study package. The first new local-model proposal receipt was
  classified unreliable and remained private negative evidence; the retry was
  stopped without a receipt after abnormal duration. No persona promotion or
  quality claim followed.
- **Privacy consequence:** Real paths, IDs, corpus metadata, private counts,
  hashes, content, labels, model output, and behavioral aggregates remain
  outside Git.
- **Non-decision:** No full-corpus snapshot, database ingestion, high-signal
  selector, permanent model choice, threshold change, annotation acceptance,
  calibration mapping, automatic promotion, or persona-quality conclusion is
  approved by this checkpoint.
- **Durable record:** [Bounded private persona pilot](bounded-private-persona-pilot-2026-07-18.md)

## Resolved Candidate History

| Candidate | Resolution |
| --- | --- |
| C-008 — Separate Mirror, Advisor or Mission, Copilot, Delegate, and Observer or Learner modes | Promoted into the working functional model by D-016 under the user's delegated design authority |
| C-009 — Use one stable personality core with scoped contextual projections | Refined and promoted by D-016 as one subconscious core plus context-specific conscious workspaces |
| C-006 — Begin with coding-agent governance before expanding toward a general virtual self | Resolved for V1 by D-025 as a coding-judgment pilot; the long-term scope remains general |
| C-010 — Support containerized local operation | Confirmed and implemented for V1 by D-026 |
| C-011 — Bootstrap a declared persona when history is absent | Confirmed with declaration-only authority and abstaining cold start by D-028; the non-personal data-free startup path is implemented by D-032 |
| C-013 — Keep the full private core local and minimize external disclosure | Strengthened by D-027 to D0-only adapter egress in V1 |
| C-015 — Use an official ChatGPT account export as one corpus source | Selected as the first supported adapter by D-027; actual export availability and content remain unverified |

## Confirmed Non-Goals

| ID | Non-goal | Reason |
| --- | --- | --- |
| N-001 | Style imitation as the sole success criterion | Style fidelity is in scope, but alone cannot establish judgment fidelity, provenance, uncertainty, or authority safety |
| N-002 | Treating every transcript item as equally authoritative | Speaker, scope, provenance, and outcome matter |
| N-003 | Untraceable or irreversible autonomous self-modification | Autonomous persistence remains in scope, but durable changes must be inspectable, evaluated, versioned, and reversible |
| N-004 | Presenting unbuilt integrations as supported | The project must not overclaim implementation |
| N-005 | Granting action authority solely from persona similarity | Drafting or imitation capability and execution authority are separate; action requires explicit, scoped permission |

## Candidates Awaiting Decision

| ID | Candidate | Why it is not confirmed | Required decision evidence |
| --- | --- | --- | --- |
| C-001 | Use the lowercase repository slug **your-next-opponent-is-you** | The remote currently preserves an uppercase initial; no rename was requested | Explicit user request to rename the remote repository |
| C-002 | Keep the title **Your Next Opponent Is You.** and its current tagline as final public copy | The proposal strongly recommends them, but final branding was not explicitly approved | Public-copy review and explicit approval |
| C-003 | Use **personal controller** as the permanent product category | It is a useful working label but may be too broad or ambiguous | Positioning research and user decision |
| C-004 | Use a structured decision-event record as the core conceptual unit | A provisional typed schema is implemented, but no real corpus shows that humans can label it reliably | Corpus sampling and annotation trial |
| C-005 | Evaluate by predicting held-out user decisions and requested evidence | The synthetic harness is implemented, but no real-user holdout or threshold exists | User-audited temporal benchmark and baseline comparison |
| C-007 | Use the phrase **Your corrections shape policy** instead of **become policy** | It avoids implying automatic promotion but changes the proposed hero copy | Copy decision |
| C-012 | Define **user-owned** as local control, inspection, export, correction, revocation, deletion, portability, and provider independence | Question 18 was delegated to the research process; this is the current proposed definition | User approval and enforceable acceptance tests |
| C-014 | Permit automatic promotion into the active core after evidence, conflict, holdout, safety, audit, and rollback gates pass | Autonomous persistence is confirmed but the exact gate and threshold are not | Corpus trial, regression suite, red-team tests, and user-visible rollback exercise |

## Open Decision Areas

No decision has been made for:

- durable full-corpus acquisition, export, ownership, consent, or retention
  beyond the bounded private study checkpoint in D-059;
- a permanent high-signal streaming selector, cursor format, audit threshold,
  or corpus-expansion rule;
- expansion beyond the coding-judgment V1 into a general personal persona;
- mission hierarchy, conflict resolution, priority, pause, resume, and
  completion semantics;
- final user-facing labels and transition presentation for the adopted working
  modes;
- annotation policy or evidence weighting;
- whether real results justify changing the confirmed V1 architecture,
  dependencies, storage, or non-parametric approach;
- a permanent local model selection and measured smaller-model comparison;
- adapters or an agent surface beyond the local CLI;
- privacy, deletion, portability, and authority guarantees beyond the
  confirmed public-code/private-mind boundary;
- permissions for reading, drafting, sending, approving, and executing;
- measurable acceptance criteria for the human-like functional continuity
  target;
- evidence and regression thresholds for automatic core promotion;
- whether a future version should allow anything beyond the current D0-only
  external-reasoner boundary;
- benchmark datasets, baselines, metrics, or acceptance thresholds;
- semantic conflict detection beyond exact normalized synthetic cases;
- public roadmap, governance, contributor model, or release strategy.

## Decision Change Rule

When a decision changes:

1. Keep the original entry.
2. Mark it **Superseded** with a date.
3. Link to the replacing decision.
4. Record the user statement or evidence that caused the change.
5. Update dependent research claims without deleting the historical trail.
