# Cognitive Core Hypothesis

> Status: technology-neutral research hypothesis
> User-confirmed metaphor: subconscious and conscious layers
> Last updated: 2026-07-15
> Boundary: this document does not claim machine sentience and does not select
> models, storage, frameworks, providers, or deployment infrastructure.

> Implementation note: D-025 through D-031 now define a bounded V1 scientific
> harness and [its implementation record](v1-implementation-record-2026-07-15.md).
> Those choices operationalize a subset of this hypothesis; they do not prove
> that the decomposition is correct and do not convert this document into
> architecture authority.

## Design Decision Being Investigated

The user wants one durable core similar to a subconscious, together with a
human-like conscious layer that can maintain identity, autobiographical
continuity, active goals, self-awareness of uncertainty, reflection, and
learning across restarts.

The strongest current functional decomposition is not one flat persona. It is
one **subconscious personality core** that informs a bounded **conscious
workspace** through an attention and retrieval gate. A metacognitive guardian
checks provenance, uncertainty, privacy, and authority. An autobiographical
stream and consolidation loop preserve continuity and learning.

~~~text
                         Dynamic mission stack
                                  |
                                  v
Sources -> Receipts -> Subconscious core -> Attention and retrieval gate
                            ^                     |
                            |                     v
                     Consolidation <- Conscious workspace -> Mode router
                            ^                     |
                            |                     v
                       Outcomes <- Actions and conversations
                                  |
                                  v
                     Metacognitive guardian
              provenance | uncertainty | privacy | authority
~~~

This is a functional map. Each box is a behavior and evidence boundary, not an
implementation component.

## Representation Planes

The latest report review exposed a required separation before the functional
layers are implemented:

1. **Evidence plane:** source events, speaker and quoted-speaker attribution,
   branches, receipts, actions, tool results, and observed outcomes.
2. **Identity interpretation plane:** source-linked candidates about beliefs,
   values, preferences, norms, goals, relationships, skills, style, and
   metacognitive habits, each with scope, time, uncertainty, dependencies, and
   contradictions.
3. **Protected control plane:** represented-person identity, privacy boundary,
   provenance requirements, authority, deletion, revocation, audit, and
   rollback rules.

An interpretation must not rewrite its source evidence. A learned personality
pattern must not rewrite the protected control plane. Cryptographic integrity
or correct attribution in the evidence plane does not prove semantic truth or
eligibility for the personality core.

Message authorship and claim ownership are separate. In particular, an
unannotated user-role turn may contain pasted or quoted third-party material;
its spans therefore keep an unknown claim holder until explicit adoption or
span attribution is reviewed. Turn role alone is not identity evidence.

## Candidate Identity Views Inside the Interpretation Plane

The latest source audit supports a more disciplined identity candidate without
claiming that personality has four natural software compartments:

1. **Behavioral pattern view:** probabilistic traits or recurring tendencies
   across contexts.
2. **Value view:** priorities and conflicts that guide tradeoffs without
   determining every action.
3. **Autobiographical view:** reconstructive links among events, life periods,
   goals, and historical selves.
4. **Personal metacognitive view:** how the represented user tends to handle
   uncertainty, evidence, questions, correction, and confidence.

Beliefs, preferences, missions, relationships, and skills are scoped,
versioned objects connected to these views rather than a fixed outer ring.
Goals may be identity-central in one period and temporary in another. A
communication style may be stable without being the reason for a judgment.

These views form **Candidate Ontology v0.1**. Their value depends on whether
humans can annotate them consistently and whether they predict later user
judgment beyond simpler retrieval and static-summary baselines.

A personal metacognitive tendency is not the same object as a protected
metacognitive control. The former is descriptive identity evidence. The latter
includes non-rewritable system requirements such as source receipts,
abstention on unread material, and explicit authority for irreversible
effects.

## 1. Subconscious Personality Core

The subconscious core is the slow, durable identity substrate. It may contain
source-linked representations of:

- identity continuity and autobiographical history;
- values and value conflicts;
- normative standards and prohibitions;
- stable and conditional preferences;
- metacognitive habits, including when to doubt or ask;
- learned procedures and skills;
- recurring goals and abandoned goals;
- relationships between contexts, decisions, actions, and outcomes;
- historical versions of the person rather than only the latest summary.

It is not the raw conversation archive and it is not one system prompt. It does
not speak or act directly. It supplies evidence and constraints to the
conscious workspace.

The listed dimensions are not a fixed stability hierarchy. Stability, scope,
and update behavior belong to each claim: a value can have contextual
exceptions, a belief can be temporary, and a communication pattern can be
long-lived. Psychometric or assigned-persona weights are candidates for
comparison, not the definition of the represented user.

An explicit user-authored instruction may become active in its declared scope
without first being inferred as a personality trait. Repeated behavior may
remain only a weak candidate. The core must preserve this difference between
what the user directly declared and what the system inferred about the user.

Every durable item must retain source, speaker, scope, time, confidence,
contradictions, dependency links, revision history, and deletion lineage.

## 2. Conscious Workspace

The conscious workspace is the temporary active state for the present moment.
It combines:

- the current situation and conversation;
- the active mission or mission stack;
- relevant memories selected from the core;
- current reasoning and competing hypotheses;
- the declared operating mode;
- known permissions and prohibitions;
- uncertainty and missing information;
- intended action, observed action, and real outcome.

It must not treat everything in the subconscious core as simultaneously
applicable. Context selection is part of judgment.

The workspace is reconstructible after a restart from durable continuity
events, but a reconstruction must be labeled as reconstruction rather than
uninterrupted subjective awareness.

## 3. Attention and Retrieval Gate

The gate decides what enters the conscious workspace. It should prefer:

1. evidence in the correct person, project, role, audience, risk, and time;
2. explicit user decisions over assistant suggestions;
3. independently supported patterns over duplicated derivatives;
4. verified outcomes over confident narrative;
5. unresolved contradiction over false consolidation.

The gate must be able to return **insufficient evidence**. Retrieval success is
not proof that a memory is true or applicable.

## 4. Dynamic Mission Stack

The user defined mission broadly as anything the individual is doing. Mission
therefore cannot be one fixed project objective. The current hypothesis is a
stack of nested, changing intentions:

~~~text
identity and values
  -> long-range life or professional direction
    -> active project or relationship mission
      -> current task goal
        -> immediate conversational or tool action
~~~

Missions may be created, paused, resumed, superseded, or conflict with each
other. Each mission needs:

- origin and owner;
- scope and affected people;
- priority and time horizon;
- success and stop conditions;
- dependencies and conflicts;
- current state and last verified outcome;
- authority granted for pursuing it.

The system should recover the active mission after interruption without
pretending that an obsolete mission is still current.

## 5. Operating-Mode Router

The user delegated the mode design to the research process. The recommended
working model keeps the modes separate and allows automatic routing while
making every selected mode visible:

- **Mirror:** selected when the user asks what they would think or do.
- **Advisor or Mission:** the default for decisions and goal pursuit; it may
  challenge the user's predicted answer while naming the disagreement.
- **Copilot:** selected for drafting, reviewing, explaining, and preparing
  artifacts while the user remains the actor.
- **Observer or Learner:** runs alongside other modes to record receipts,
  outcomes, and lesson candidates.
- **Delegate:** selected only when an explicit authority lease permits the
  destination, action type, scope, duration, and risk.

The router may switch among Mirror, Advisor, Copilot, and Learner when the task
requires it, but it must log and expose material switches. It may never infer
or self-grant a transition into Delegate mode.

Every output should eventually carry an envelope similar to:

~~~yaml
mode: declared operating mode
mission: active goal reference
confidence: calibrated judgment
evidence_receipts: sources actually inspected
unknowns: missing or conflicting information
authority: allowed action scope
proposed_action: optional
action_receipt: required if an action is claimed complete
~~~

An authority lease must also distinguish reversible local changes, effects
that can be staged before release, externally committed effects that permit
only compensation, and irreversible effects that require prevention or
explicit confirmation. A generic rollback promise is not sufficient.

## 6. Unknown-to-Learning Loop

The user's desired behavior is not merely to abstain. It is to ask, learn, and
remember so the same uncertainty can be resolved later.

~~~text
Detect unknown
  -> verify that no valid source already answers it
  -> ask the smallest useful question
  -> record the user's answer as explicit evidence
  -> attach scope, time, provenance, and confidence
  -> persist it through the consolidation policy
  -> retrieve it in a materially similar future context
  -> revalidate when context or later outcomes disagree
~~~

Asking is not failure when the information was unavailable. Fabricating an
answer instead of asking is failure. Repeatedly asking a question that valid
memory already answers is also a measurable memory failure.

## 7. Autonomous Consolidation Envelope

The user wants persistence and self-improvement to be autonomous. The research
recommendation is **bounded autonomous consolidation**, not a manual approval
dialog for every memory and not uncontrolled self-rewriting.

### Level A — Automatic observation

Persist source receipts, conversation events, intentions, actions, tool
results, failures, and outcome receipts automatically. Observation must not be
rewritten into interpretation.

### Level B — Automatic candidate learning

Persist inferred preferences, lessons, rules, and skill candidates
automatically with confidence, scope, evidence dependencies, and conflict
markers. Candidate status must remain visible.

### Level C — Automatic core promotion

Permit a candidate to affect the active personality core without per-item
approval only if a future policy can prove all required conditions, such as:

- sufficient explicit or independently supported evidence;
- correct scope and temporal validity;
- no unresolved high-impact contradiction;
- successful replay or holdout evaluation;
- no provenance, privacy, or authority regression;
- a versioned checkpoint and mechanical rollback path;
- an audit event visible to the user.

The exact thresholds are open research questions. Frequency alone is not
enough.

### Level D — Protected boundaries

The system may never autonomously:

- expand its own read, send, execution, or approval authority;
- weaken provenance or hallucination gates;
- export the personality core or raw history;
- make another person's identity public;
- disable deletion, revocation, audit, or rollback;
- redefine who the represented person is.

Autonomy means that learning can continue without constant supervision inside
a user-defined safety envelope. It does not mean hidden, irreversible, or
self-authorizing change.

## 8. Autobiographical Continuity

Continuity should be represented through a verifiable event stream:

- what the system believed the current mission was;
- what information it actually inspected;
- what it intended to do;
- what it was allowed to do;
- what it actually did;
- what result was observed;
- what the user later accepted or corrected;
- what lesson was proposed or promoted;
- which earlier belief was superseded.

This supports a functional self-model without claiming a private subjective
experience that cannot be tested.

## 9. Private Core and External Reasoning

Two confirmed goals create a research tension:

1. use external agent or LLM reasoning capability;
2. never upload a person's identity or personality core elsewhere.

The current candidate boundary is:

- raw conversations, derived identity, the full core, and cross-context
  behavioral profiles remain inside the user's controlled private boundary;
- an external reasoner receives only the minimum task information explicitly
  allowed for that request;
- generic external proposals are evaluated, selected, or rejected by the
  private controller;
- outbound messages are deliberate outputs with destination and action
  receipts, not exports of the internal mind;
- public source code contains schemas and synthetic fixtures, never a real
  person's mind.

Even a small personalized instruction can reveal identity information. A
threat model must determine whether any derived personal context may cross the
boundary. If the answer is no, final personalization must occur entirely
inside the private boundary. This constraint may materially affect later
architecture selection, but it does not select that architecture now.

## 10. Testable Claims

The hypothesis should be rejected or revised if the system cannot:

- resume the correct mission after interruption;
- distinguish core identity from temporary conscious state;
- select relevant memories without cross-scope leakage;
- say what it knows, how it knows it, and what it has not read;
- ask once, learn with provenance, and reuse the answer later;
- improve automatically without degrading held-out behavior;
- roll back a harmful learned change;
- keep private identity material inside the approved boundary;
- distinguish advice from predicted persona behavior;
- prevent learning autonomy from becoming action-authority escalation.

## 11. What Remains Unresolved

- whether the subconscious/conscious metaphor maps cleanly enough to an
  annotatable schema;
- how mission conflicts and priorities are learned;
- what evidence threshold permits automatic core promotion;
- how to test continuity without rewarding persuasive self-narration;
- what minimal context, if any, may be sent to an external reasoner;
- how the user inspects and repairs a wrong core belief efficiently;
- whether a real-time conscious workspace needs one reasoning process or
  several independently checked processes;
- how to prevent malicious conversation content from becoming subconscious
  identity evidence.
