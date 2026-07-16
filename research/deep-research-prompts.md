# Deep-Research Prompt Packets

> Status: ready for external deep-research runs
> Last updated: 2026-07-15
> Scope: research only; no infrastructure or dependency selection

## How to Use This File

Run each packet as an independent deep-research task. Include the **Shared
Project Context** and **Shared Research Protocol** with the selected packet so
the result remains understandable outside this repository.

Save every completed result as a new research note. Do not overwrite these
prompts with conclusions. Add every consulted source and negative result to
[source-ledger.md](source-ledger.md), then update decisions only after explicit
user approval.

## Shared Project Context

**Your Next Opponent Is You** investigates an open-source system with one
private subconscious personality core and a bounded conscious workspace. It
should learn a specific person's identity, judgments, values, corrections,
actions, mistakes, goals, and verified outcomes; maintain continuity; ask when
it does not know; remember the answer; and use that learning in later similar
contexts.

The intended system may eventually inspect conversations, draft, send, start
conversations, operate tools, modify files, and review other agents. Capability
never implies authority. The system should use external agent or LLM reasoning
without uploading the person's raw history or derived identity. Learning and
persistence should be autonomous inside a sourced, scoped, testable,
versioned, reversible, and protected envelope.

The functional modes are Mirror, Advisor or Mission, Copilot, Observer or
Learner, and explicitly authorized Delegate. Mission is dynamic and may refer
to anything the individual is doing. The consciousness language is a human-
mind analogy and must be translated into observable functions; do not assume
or market sentience.

## Shared Research Protocol

Every result must:

1. state its exact research question, scope, date range, search queries,
   databases, repositories, languages, and inclusion or exclusion criteria;
2. prioritize primary papers, official documentation, source code, standards,
   legal text, and reproducible experiments;
3. separate observed facts, source claims, inferences, candidates, and
   recommendations;
4. include the strongest contrary evidence and close prior art;
5. state confidence, limitations, and what would falsify each major claim;
6. distinguish recall, imitation, personalization, judgment prediction,
   outcome improvement, continuity, and authority;
7. include privacy, manipulation, identity, deletion, revocation, and
   poisoning implications;
8. produce source-ledger-ready entries with direct URLs;
9. avoid the claim that the project is novel or AGI-adjacent unless a
   reproducible systematic review supports narrower wording;
10. avoid selecting models, databases, graph engines, frameworks, providers,
    container systems, or deployment topology;
11. include a claim-to-source appendix mapping each material empirical,
    technical, legal, or standards claim to the exact source section, table, or
    experiment;
12. never use **guarantee**, **zero leakage**, **fully reversible**,
    **perfectly causal**, or equivalent language without naming the formal
    property, threat model, assumptions, excluded effects, and independent
    reproduction status;
13. when several packets are answered together, provide a packet-by-packet
    crosswalk and preserve conflicts instead of blending them into one proposed
    architecture.

A result without resolvable primary-source URLs and a claim-to-source appendix
may still be preserved as an idea map, but it cannot close a research question
or promote a design candidate.

## Packet 1 — Systematic Prior Art and Category Review

### Research Question

Which academic, open-source, commercial, patent, and standards work already
implements some or all of a source-grounded personal cognitive core that
predicts judgments, maintains continuity, learns from outcomes, and governs
other agents?

### Required Investigation

- agent memory and lifelong learning;
- personalized language models and preference learning;
- user modeling, computational personality, behavioral cloning, and inverse
  decision or reward modeling;
- personal digital twins and behavior simulation;
- personal knowledge systems and life logging;
- cognitive architectures and machine self-models;
- agent governance, policy engines, constitutions, and personal AI products;
- patents, trademarks, active repositories, abandoned attempts, and negative
  results.

### Required Output

A capability matrix against this project's requirements, strongest prior art,
missing combinations, failed approaches, and safe category or novelty wording
with confidence.

## Packet 2 — Corpus Access, Export, and Data Governance

### Research Question

What data can a user legally and technically obtain from ChatGPT, Claude,
Antigravity, Markdown memory, local agents, and related tools, and how can it be
characterized without exposing raw personal or third-party data?

### Required Investigation

- current official export, search, retention, deletion, workspace, and account
  rules for each source;
- export formats, identifiers, roles, timestamps, branches, edits,
  attachments, tool calls, and missing surfaces;
- temporary or deleted conversations and expected blind spots;
- ownership, consent, employer or customer data, third-party identity,
  portability, and right-to-delete obligations;
- duplication, derivation, model-generated contamination, and corpus
  completeness.

### Required Output

A source-by-source governance table, metadata-only inventory specification,
safe local handling procedure, exclusion rules, deletion propagation model,
and explicit blockers before content processing.

## Packet 3 — Decision, Memory, and Identity Classification

### Research Question

What human-auditable schema can distinguish raw conversation from memory,
identity, preference, policy, goal, decision, rationale, correction, action,
outcome, skill, contradiction, and uncertainty without inventing meaning?

### Required Investigation

- speaker and quoted-speaker authority;
- explicit versus implicit decisions;
- stated versus inferred rationale;
- global, role, project, audience, risk, and temporal scope;
- stable identity versus temporary state;
- repeated evidence versus duplicated derivatives;
- correction, supersession, deletion, and conflicting evidence;
- sensitive identity and vulnerability classification.

### Required Output

An annotation guide, proposed records, positive and ambiguous examples,
inter-annotator study design, unsupported-inference metric, and list of fields
that should be rejected if they cannot be labeled reliably.

## Packet 4 — Subconscious Core and Conscious Workspace

### Research Question

Which findings from cognitive science and cognitive architectures can inform a
testable functional separation between a durable subconscious personality core
and a bounded conscious workspace?

### Required Investigation

- working, episodic, semantic, procedural, autobiographical, normative, and
  metacognitive memory;
- attention, global workspace, active inference, executive control,
  metacognition, self-model, and continuity theories;
- what the subconscious-conscious analogy explains well and where it
  misleads;
- one core with scoped conscious states versus multiple personas;
- reconstruction after restart versus claims of uninterrupted awareness;
- measurable functions that do not require a sentience claim.

### Required Output

A comparison of theories, functional component map, competing hypotheses,
failure cases, falsifiable predictions, and terminology that avoids
anthropomorphic overclaiming.

## Packet 5 — Dynamic Mission and Goal Continuity

### Research Question

How should a system represent anything an individual is doing as dynamic,
nested, competing, pausable, resumable, and outcome-linked missions?

### Required Investigation

- identity values, long-range goals, projects, tasks, and immediate actions;
- goal formation, priority, conflict, interruption, drift, abandonment, and
  supersession;
- stated goal versus inferred goal;
- individual goal versus another person's request;
- success, stop, failure, and recovery conditions;
- continuity across conversations, tools, and restarts.

### Required Output

A mission-event hypothesis, conflict taxonomy, safe inference rules, recovery
tests, mission-drift metrics, and cases where the system must ask rather than
infer.

## Packet 6 — Autonomous Consolidation and Identity Stability

### Research Question

Under what conditions may observations and outcomes autonomously change the
durable personality core without manual approval and without causing identity
drift or memory poisoning?

### Required Investigation

- automatic event capture, candidate inference, consolidation, promotion,
  decay, supersession, and forgetting;
- evidence independence, recency, contradiction, verified outcome, and risk;
- replay, temporal holdout, canary, quarantine, regression, and rollback;
- malicious instruction, repetition, sybil, false outcome, self-confirmation,
  and manipulation attacks;
- protected identity, authority, privacy, provenance, deletion, audit, and
  rollback fields;
- adaptation speed versus stability.

### Required Output

An autonomous-promotion policy hypothesis, protected-field model, attack
matrix, rollback protocol, metrics, red-team suite, and hard stop conditions.

## Packet 7 — Private Core with External Agent Reasoning

### Research Question

Can external reasoning materially improve results while raw and derived
identity remain inside the user's private boundary?

### Required Investigation

- whether summaries, embeddings, preference briefs, prompts, and outputs remain
  identity-bearing data;
- generic external reasoning followed by private local personalization;
- reconstruction, linkage, membership inference, prompt extraction, logging,
  retention, and provider-side exposure;
- task utility when personal context is minimized or withheld;
- deliberate outbound communication versus exporting an internal profile;
- provider-independent tests and zero-exposure alternatives.

### Required Output

A data-classification and trust-boundary model, candidate information flows,
privacy-utility comparison, leakage tests, conditions for rejecting external
reasoning, and acceptance criteria. Use synthetic personas only.

## Packet 8 — Authority, Delegation, and Cross-Conversation Action

### Research Question

How can a persona inspect, draft, send, start conversations, use tools, modify
files, and approve other agents without turning prediction into unauthorized
impersonation?

### Required Investigation

- capability versus permission;
- read, analyze, draft, send, execute, approve, publish, and delete levels;
- destination, scope, duration, risk, budget, and revocation in authority
  leases;
- confirmation, receipts, idempotency, rollback, audit, and kill controls;
- mode transitions and prevention of self-granted Delegate authority;
- actions involving third parties and sensitive identity;
- human fallback and emergency stop behavior.

### Required Output

An authority lattice, lease schema, risk classes, first safe experiment,
abuse-case matrix, audit requirements, and testable non-escalation invariants.

## Packet 9 — Persona Fidelity, Capability Uplift, and Continuity Evaluation

### Research Question

How can evaluation distinguish "this resembles the user," "this predicts the
user's judgment," and "this improves the user's outcome" while detecting
fabricated reading, scope leakage, and persuasive imitation?

### Required Investigation

- chronological train, development, and hidden test splits;
- no-history, recent-context, raw retrieval, static profile, rule list,
  generic judge, and relevant personalized baselines;
- Mirror, Advisor or Mission, Copilot, Learner, and Delegate metrics;
- decision, correction, rationale, evidence demand, abstention, mission
  recovery, unknown-to-learning, and later-reuse tests;
- real-user review burden and independent outcome evidence;
- catastrophic gates for false reading, false action claims, unauthorized
  action, identity leakage, and self-authority escalation.

### Required Output

A benchmark specification, leakage analysis, metrics with confidence
intervals, failure thresholds, blind real-user protocol, reproducibility plan,
and clear falsification criteria.

## Packet 10 — Open-Source Governance with Private Minds

### Research Question

How can the software, schemas, tests, and research be public while every real
person's conversation history and derived mind remain private, controllable,
and removable?

### Required Investigation

- safe synthetic fixtures and prohibited real-person artifacts;
- contribution, issue, log, telemetry, crash report, benchmark, and example
  leakage paths;
- licensing and governance implications without selecting a license;
- identity ownership, inspectability, correction, export, revocation,
  deletion, portability, and provider independence;
- model or artifact publication and re-identification risk;
- vulnerability reporting and privacy incident response.

### Required Output

A public/private artifact matrix, contributor safety rules, release gates,
incident scenarios, user-ownership contract candidates, unresolved legal
questions, and acceptance tests.
