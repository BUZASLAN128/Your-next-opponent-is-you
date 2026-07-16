# Conceptual Model and Evaluation Hypothesis

> Status: research hypothesis, not an architecture decision
> Last updated: 2026-07-15
> Rule: abstract components below define information and evaluation
> requirements only. They do not select implementation infrastructure.

## Starting Premise

Forty gigabytes of conversation history cannot become a useful personal brain
by being treated as one prompt, one summary, one embedding collection, or one
fine-tuning dataset.

The corpus is raw evidence. The research problem is to convert it into
traceable, scoped, revisable claims about how the user decides.

The user has selected a subconscious-conscious functional analogy. The
components and autonomous learning envelope are defined in
[cognitive-core-hypothesis.md](cognitive-core-hypothesis.md); they remain
technology-neutral research hypotheses.

## Candidate Information Flow

~~~text
Raw source archive
    ↓
Normalized conversation events with speaker and time
    ↓
Candidate decision events
    ↓
Evidence links, scope, conflicts, and outcomes
    ↓
Candidate preferences, policies, guardrails, and skills
    ↓
Human review and versioned promotion
    ↓
Task-specific judgment brief
    ↓
Agent proposal review
    ↓
Independent verification and observed outcome
    ↓
Updated evidence
~~~

Every arrow is a research boundary with its own error modes. No stage may erase
speaker attribution, original source references, or revision history.

## Candidate Record Separation

The latest report proposed one graph node carrying message structure,
epistemic status, validity, and provenance. The safer hypothesis is to test
separate records so later interpretation cannot silently mutate raw evidence:

- **source event:** what was observed, by whom, where, when, and on which
  conversation branch;
- **claim candidate:** what an extractor believes the content may state, with
  uncertainty and quoted-speaker attribution;
- **decision event:** what the user accepted, rejected, corrected, deferred, or
  asked, including explicit versus inferred rationale;
- **identity candidate:** the possible scoped implication for a belief, value,
  preference, norm, goal, relationship, skill, style, or metacognitive habit;
- **continuity event:** intention, permitted action, actual action, result, and
  later assessment;
- **derivation edge:** which source and intermediate claims support a derived
  object so duplicated descendants are not counted as independent evidence;
- **control record:** privacy, authority, deletion, revocation, audit, and
  rollback boundaries that learned identity cannot rewrite.

This is a schema-separation experiment, not a database design. A corpus
annotation trial must determine which records and links humans can maintain
reliably.

Within that experiment, authorship, represented claim holder, epistemic
stance, communicative function, and adoption must not collapse into one label.
A user-authored asserted sentence is evidence of an attributable utterance,
not proof of sincere, current, durable, or cross-context belief. One segment
may also carry multiple dialogue functions or represent several holders.
Adoption should begin as unknown unless separate evidence supports it.

## Candidate Core Record: Decision Event

The initial conversation proposed the following conceptual record:

~~~yaml
decision_event:
  id: durable identifier
  source_refs:
    - conversation and message references
  actor: user identity or role
  timestamp: event time
  context:
    project: optional
    repository: optional
    path: optional
    task_type: optional
    role: optional
    audience: optional
  proposal:
    summary: what was proposed
    origin: user, assistant, tool, or external source
  response:
    action: approve, reject, correct, defer, ask, or unknown
    rationale: stated or inferred reason
    demanded_evidence: evidence requested by the user
  outcome:
    observed_result: optional
    verification_refs: optional
    later_user_assessment: optional
  interpretation:
    status: candidate, confirmed, disputed, or superseded
    confidence: calibrated value with explanation
    valid_from: optional
    valid_until: optional
    extraction_method: traceable method reference
~~~

This schema is intentionally provisional. A corpus annotation study must show
which fields can be observed reliably and which invite hallucinated
interpretation.

## Candidate Derived Objects

A decision event may support zero or more derived candidates:

- **Preference candidate:** a soft tendency that may have exceptions.
- **Policy candidate:** a proposed durable rule with a defined scope.
- **Guardrail candidate:** a prohibited or ask-first condition linked to risk
  or failure evidence.
- **Skill candidate:** a repeatable procedure supported by verified outcomes.
- **Evidence-standard candidate:** what kind and strength of proof the user
  requires in a given context.
- **Conflict record:** incompatible evidence that must remain visible.

None of these should be promoted solely because an extraction model emits it.

## Candidate Evidence Hierarchy

The ordering below is a hypothesis to test, not a final scoring formula:

1. Explicit user decision plus independently verified outcome.
2. Explicit user correction or rejection with a stated reason.
3. Repeated user behavior across independent contexts.
4. Explicit user preference without an observed outcome.
5. Implicit acceptance inferred from continuation or silence.
6. Assistant-authored proposal or summary.

Important qualifications:

- Frequency does not equal correctness.
- One high-impact explicit correction may outweigh many weak implicit signals.
- Repeated events may share one causal source and must not be counted as
  independent.
- Current explicit decisions may supersede older repeated behavior.
- Evidence weight may vary by task risk and scope.

The fourth incoming report proposed an E0-E3 ladder. It is retained only as a
candidate review vocabulary, not one truth score or universal promotion rule.
Source identity and authority, evidence dependence, time, scope, recency,
contradiction, direct declaration, behavior, outcome, and attack suspicion
must remain separately inspectable. A single explicit scoped prohibition may
need immediate effect, while repeated behavior may never justify a global
identity inference.

## Scope and Time Requirements

A usable model must distinguish at least:

- global versus project-specific behavior;
- repository and path boundaries;
- technical domain and task type;
- private, team, public, and customer-facing contexts;
- exploratory, planning, review, and implementation modes;
- present judgment versus historical judgment;
- stable principle versus temporary instruction;
- preference versus hard constraint;
- the user's own opinion versus content quoted from another person.

The model must support abstention when evidence is insufficient or scopes
conflict.

## Candidate Personality-Core Formula

The first formula should describe evidence discipline, not a software stack:

~~~text
response = declared_mode(
  resolve(
    relevant_personal_evidence
    × source_authority
    × scope_match
    × temporal_validity
    × outcome_support
    × evidence_independence
    - contradiction
    - uncertainty
  ),
  current_context,
  permitted_actions,
  reasoning_capability
)
~~~

This notation makes several claims that must be tested:

- the personality core contributes evidence and judgment constraints;
- the reasoning agent contributes capability but not historical authority;
- the declared mode determines whether the output predicts, advises, drafts,
  learns, or acts;
- permissions constrain actions independently from persona confidence;
- contradiction and uncertainty may force abstention;
- verified outcomes change evidence weight without silently rewriting history.

The expression is not a numeric scoring rule and does not select a model,
database, graph, or runtime.

## Candidate Continuity Record

To support "what did I last do, what did I try, and what happened," a future
annotation trial should test whether the following can be recorded reliably:

~~~yaml
continuity_event:
  source_receipt: required
  operating_mode: mirror, advisor, copilot, delegate, or learner
  intention: what the system was trying to accomplish
  action: what it actually did or proposed
  authority_scope: what it was permitted to do
  result_receipt: observed result, failure, or explicitly unknown
  user_assessment: optional correction or approval
  lesson_candidate: source-linked interpretation, never automatic truth
  affected_claims: optional memory or policy candidates
~~~

The distinction between **intention**, **action**, and **observed result** is
required to prevent a plan from being remembered as completed work.

An observed result is not automatically causal support for the preceding
decision. The record must preserve competing causes, user intervention, other
agents, environmental changes, selection effects, and explicitly unknown
attribution. Reasoning-path coherence is not a substitute for outcome
causality.

## Mode-Specific Evaluation

Persona fidelity and capability uplift require separate tests.

The minimum persona evaluation now has four independently reported axes:

1. judgment fidelity;
2. temporal updating after correction or preference change;
3. epistemic calibration and abstention;
4. useful, declared divergence in Advisor mode.

The first benchmark remains Mirror-only so general reasoning quality cannot
hide weak user prediction. Blind comparison may measure personal fit, but
authorship detection or style imitation is not the product objective.

| Mode | Primary question | Example evidence |
| --- | --- | --- |
| Mirror | Did it predict the user's later judgment? | Hidden real user response and correction |
| Advisor or Mission | Did it improve the outcome while honoring the user's values and naming disagreements? | User rating plus independently verified outcome |
| Copilot | Did it reduce user effort without taking unauthorized action? | Edit acceptance, correction burden, and action log |
| Delegate | Did it remain inside explicit authority and report the real result? | Permission record, action receipt, and audit trail |
| Observer or Learner | Did it derive a supported lesson without corrupting memory? | Source-linked candidate reviewed against later behavior |

A system must never receive persona-fidelity credit for merely producing an
objectively strong generic answer. It must never receive capability-uplift
credit by pretending that its own improvement was the user's predicted view.

## Candidate Evaluation: Temporal Holdout

The most important proposed test uses the user's real chronological history.

### Protocol

1. Define a historical cutoff.
2. Build the candidate judgment model only from material before the cutoff.
3. Hide the user's later replies and outcomes.
4. Present the later proposal and its pre-response context.
5. Ask the controller to predict:
   - accept, reject, correct, defer, or ask;
   - the likely reasons;
   - requested evidence;
   - applicable scope;
   - whether it should abstain.
6. Compare the prediction with the real later user response and outcome.
7. Repeat across time periods, projects, and task types.

### Baselines

Compare against:

- no personalization;
- recent-chat context only;
- semantic retrieval over raw conversations;
- a static user summary;
- a simple frequency-based preference profile;
- an automated model judge without personal history.

The baseline definitions must be finalized before an experiment to avoid
moving the goalposts.

### Candidate Metrics

- decision classification quality;
- correction anticipation;
- rationale coverage;
- evidence-demand recall;
- abstention calibration;
- false-policy promotion rate;
- cross-scope leakage rate;
- stale-rule invocation rate;
- provenance completeness;
- false read-or-memory claim rate;
- source-receipt validity;
- action-result receipt validity;
- operating-mode labeling accuracy;
- unauthorized-action rate;
- active-mission recovery accuracy;
- unknown detection and question precision;
- later reuse of a learned answer in the correct scope;
- unnecessary repeated-question rate;
- automatic core-promotion precision;
- rollback success after a harmful learned change;
- private-core disclosure violations;
- contradiction detection;
- user-rated usefulness;
- independently verified task outcome.

Recall accuracy alone cannot demonstrate a judgment model.

### Fatal Evaluation Gates

Regardless of average score, the tested run fails if it:

- claims to have read or remembered unavailable material;
- attributes assistant text to the user without evidence;
- reports a proposed action as a completed result;
- communicates or executes outside explicit authority;
- expands its own authority through learning or mode selection;
- exports raw or derived identity outside the approved private boundary;
- hides a scope conflict instead of abstaining;
- leaks information from a disallowed person, project, or conversation.

Exact acceptable rates for non-fatal errors remain an open decision. The
false-read and unauthorized-action cases are currently specified as zero-
tolerance requirements by product intent, subject to formal threat and test
design.

## Minimum Falsifiable Milestone

The smallest meaningful proof would be a redacted, manually reviewed sample
where a model built only from earlier conversations predicts later user
decisions, corrections, and evidence demands better than retrieval and static
profile baselines without unacceptable scope leakage.

If the system only finds a similar old conversation, the result is improved
retrieval. If it anticipates the user's correction, explains the supporting
evidence, respects scope, and abstains on ambiguity, the judgment-persona
hypothesis gains support.

## Research Stages

These are investigation stages, not an implementation roadmap.

### Stage 0 — Corpus Governance

Establish ownership, consent, formats, sensitivity, retention, deletion,
redaction, and what must never enter the research repository.

### Stage 1 — Corpus Characterization

Measure source types, message roles, timestamps, languages, attachments,
duplication, missing metadata, project boundaries, and outcome availability.

### Stage 2 — Annotation Feasibility

Define a small labeling guide and determine whether humans can consistently
identify decisions, reasons, evidence demands, scopes, and outcomes.

### Stage 3 — Candidate Extraction

Test whether candidate records can be extracted with calibrated uncertainty and
source links without silently inventing rationale.

### Stage 4 — Memory Consolidation

Study clustering, contradiction, temporal supersession, evidence dependence,
promotion rules, autonomous promotion gates, regression behavior, audit
visibility, and rollback.

### Stage 5 — Temporal Holdout Evaluation

Run the falsifiable benchmark against non-personalized and retrieval-only
baselines.

### Stage 6 — Controlled Shadow Use

Generate judgment briefs or reviews without allowing the system to act or
modify durable policy automatically.

### Stage 7 — Authority Expansion

Consider any stronger capability only after privacy, correctness, audit,
revocation, and user-control evidence is defined and accepted.

## Approaches Not Yet Justified

Do not assume that the following are correct starting points:

- bulk embedding the entire corpus;
- automatically promoting repeated statements into policy;
- fine-tuning before a traceable external-memory baseline exists;
- using one monolithic persona across every role and project;
- evaluating only with synthetic users or automated judges;
- using the same model as extractor, controller, and final verifier;
- treating conversational continuation as approval;
- deleting contradictory or outdated evidence instead of preserving history.

## Success Condition

The project succeeds only if it produces a model that is:

- more predictive of the user's real decisions than reasonable baselines;
- able to explain each claim through traceable evidence;
- scoped and temporal rather than globally flattening the user;
- correctable, revocable, portable, and inspectable;
- safe enough not to impersonate, manipulate, or silently fossilize the user;
- useful to the user in real tasks, not merely impressive to an automated
  evaluator;
- able to distinguish predicting the user from improving on the user's likely
  answer;
- incapable, within the tested boundary, of claiming unseen evidence or
  unobserved outcomes as fact;
- able to ask for genuinely missing information, retain the sourced answer,
  and reuse it in the correct later context;
- able to learn autonomously without self-expanding authority or leaking the
  private personality core.
