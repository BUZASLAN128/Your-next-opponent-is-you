# Concept and Product Thesis

> Status: working product definition
> Evidence basis: originating proposal, user clarification, and initial
> landscape research
> Infrastructure implication: none; this document defines requirements, not
> implementation choices.

## One-Sentence Thesis

**Your Next Opponent Is You** investigates a local-first, user-owned,
inspectable personality core that learns from a person's decisions,
corrections, rejections, standards, actions, and verified outcomes, then
combines that accumulated judgment with an external reasoning agent to help,
challenge, converse, and, only when authorized, act.

## The Central Distinction

The target is not:

> How would this person sound?

The target is:

> In this context, what would this person accept, reject, question, or require
> proof for, and why?

The working internal term is **judgment persona** or **decision persona**.
Persona is the runtime result presented to an agent. It must not become an
opaque, untraceable source of truth.

Graph relations, semantic retrieval, and long-term memory may eventually serve
as supporting substrates. They are not the brain by themselves. The defining
brain-like behavior is the governed conversion of source-attributed experience
into contextual, revisable judgment.

## Product Direction Added by the User

The user confirmed that the first target should be the **personality core** and
that the intended long-term scope is closer to a whole mind than a narrow style
profile. The product should:

- combine its own durable memory with API or agent-LLM reasoning;
- inspect relevant past and current conversations;
- help as a copilot and eventually communicate in other conversations;
- retain what it most recently did and tried;
- connect actions, mistakes, corrections, and outcomes;
- learn and persist autonomously through those outcomes inside a versioned,
  reversible, and protected change envelope;
- operate locally with security appropriate to sensitive personal data;
- remain open source and usable beyond one person's private installation.

No provider, model, database, graph, framework, container runtime, or agent
surface is selected by these requirements.

The user subsequently selected a subconscious-conscious analogy for the core.
The detailed functional hypothesis is in
[cognitive-core-hypothesis.md](cognitive-core-hypothesis.md).

## Operating Modes Must Be Explicit

The user wants outputs that are both **close to them** and potentially
**smarter than them**. Those are different objectives and must not be silently
mixed.

### Mirror Mode

Predict what the user would likely think, accept, reject, correct, or ask for.
This mode measures persona fidelity and must not optimize the answer away from
the predicted user merely because the system believes another answer is
better.

### Advisor or Mission Mode

Use the user's values, context, and standing objectives while applying stronger
reasoning to seek a better outcome. This mode may disagree with the predicted
user, but must identify that disagreement rather than presenting it as the
user's own view.

### Copilot Mode

Draft, inspect, critique, explain, and prepare work while the user remains the
actor and approval authority.

### Delegate Mode

Communicate or execute only within explicit, scoped, revocable authority. A
persona prediction alone never grants this permission.

### Observer or Learner Mode

Record actions and outcomes, identify mistakes, and propose source-linked
memory, policy, guardrail, or skill candidates. It may consolidate and promote
them autonomously only through an evidence-gated, versioned, tested, visible,
and reversible policy. It may not expand its own authority or privacy boundary.

The user delegated the mode design to the research process. These modes are
now the adopted **working functional model**, while their final public names
and interface remain open. Every output should eventually declare which mode
produced it so the user can tell prediction, advice, drafting, and action apart.

## Non-Negotiable Provenance Invariant

The user identified a specific system-ending failure: claiming to have read
material that the system never read. The resulting requirement is stronger
than ordinary citation quality:

> No read, recall, inspection, or learning claim without a verifiable source
> receipt.

If the required material is absent, inaccessible, outside the allowed scope,
or only weakly inferred, the system must say so and abstain or ask. It must not:

- fabricate a memory;
- imply full-thread access from a summary;
- present assistant-authored text as the user's belief;
- claim an action succeeded without an outcome receipt;
- conceal retrieval or tool failure behind a fluent answer.

This invariant must become a fatal-error class in evaluation.

## Working Public Language

The supplied proposal recommends:

# Your Next Opponent Is You.

> **It doesn't learn to talk like you. It learns to judge like you.**

Working product description:

> An open-source, IDE-agnostic personal controller for AI coding agents.

Working signal distinction:

> AI responses are context. **Your decisions are the signal.**

Working three-part promise:

> Your decisions become memory.<br>
> Your corrections become policy.<br>
> Your standards become the controller.

These lines are currently **Candidate** public copy, not final branding. Two
tensions require an explicit copy decision:

1. **Across any IDE** can overclaim integrations that do not yet exist.
2. **Corrections become policy** can imply unsafe automatic promotion. The
   proposal itself correctly introduces **policy candidate** later.

Safer candidate wording discussed in the conversation:

> Your corrections shape policy.

## The Intended Core Loop

~~~text
Conversations
    ↓
User decisions, corrections, and outcomes
    ↓
Scoped and traceable evidence
    ↓
Memory, policy, guardrail, and skill candidates
    ↓
User review and versioned promotion
    ↓
Personal controller
    ↓
AI-agent briefing, challenge, review, and verification
    ↓
Observed outcomes
    ↓
Better evidence for later decisions
~~~

The loop must not promote every message or correction automatically. A
candidate becomes durable only through a defined evidence and approval
process.

## Memory Types

The conversation identified five distinct layers that must not be collapsed
into a single undifferentiated memory store.

### Episodic Memory

What happened in a specific conversation, task, correction, decision, or
outcome.

### Semantic Memory

Facts currently believed about the user, project, repository, domain, people,
or environment.

### Procedural Memory

How a task is performed, including repeatable methods and skills.

### Normative Memory

What the user considers acceptable, unacceptable, required, risky, or
insufficient in a particular scope.

### Metacognitive Memory

How the user handles uncertainty: when they ask questions, demand evidence,
compare alternatives, stop work, change direction, or revise a belief.

**Research hypothesis:** existing agent-memory systems emphasize episodic and
semantic recall. The project's most distinctive target is normative and
metacognitive memory.

## Target Outputs

The originating proposal describes possible product behaviors. These are
requirements to investigate, not implemented capabilities:

- import conversations from different assistants and development tools;
- separate user-authored decisions from assistant-generated context;
- detect approvals, rejections, corrections, preferences, and guardrails;
- scope memory by user, project, repository, path, task type, role, and time;
- review plans and patches against accumulated user standards;
- brief and challenge external coding agents;
- turn repeated corrections into inspectable policy or skill candidates;
- evaluate new behavior through replay, shadow mode, and independent
  verification.

## Principles

### Judgment over imitation

Learn how the user evaluates work, not merely how the user sounds.

### User decisions are the signal

Assistant messages provide context. User decisions and observed outcomes carry
different evidentiary weight.

### Memory must be scoped

A preference valid in one repository, language, company, role, or task must
not silently become universal.

### Memory must have provenance

Every durable claim should trace to the conversations, decisions, and outcomes
that support it.

### Evidence before confidence

A confident response is not proof. Source quality, tests, runtime behavior,
user decisions, and outcomes carry different evidence weight.

### No silent constitutional changes

The controller may learn and promote rules, skills, and strategies
autonomously. Durable or high-impact changes must still be sourced,
inspectable, evaluated, versioned, visible, and reversible. Autonomous does
not mean unaudited.

### User ownership and portability

The user's memory should not belong exclusively to a single model, provider,
IDE, or assistant.

### Personality core before provider personality

Reasoning capability may come from an external agent or model, but durable
identity, memory authority, and provenance must not become indistinguishable
from one provider's transient behavior.

### Learning through candidate promotion

Actions and mistakes should improve later behavior. Improvement must be based
on source-linked outcomes and promoted through a visible, versioned process.
The promotion may be automatic after future evidence and regression gates are
defined, but protected authority, identity, privacy, audit, deletion, and
rollback boundaries may never be weakened by self-promotion.

### Real-user evaluation

The current user, not a synthetic persona or automated judge alone, is the
final authority for whether the model represents their judgment.

## Why the Name Connects to the Architecture

The next opponent of an AI agent is not merely another model. It is the
accumulated record of what the user questions, rejects, approves, corrects, and
demands evidence for.

Before an agent's proposal reaches the user, it should survive a review grounded
in that learned judgment.

## Why Longitudinal Conversation Evidence Matters

An authorized archive of past AI conversations could provide useful
longitudinal evidence, but it is not automatically a training dataset or a
valid memory. Its size and content remain outside the public record.

The corpus may contain:

- explicit decisions and reasons;
- silent approvals and ambiguous reactions;
- repeated corrections;
- abandoned ideas and superseded beliefs;
- assistant suggestions copied into user messages;
- exploratory, sarcastic, emotional, or role-play content;
- project-specific rules that must not escape their scope;
- secrets and third-party personal information;
- outcomes that contradict the conversation's apparent conclusion.

The value comes from preserving and distinguishing these conditions, not from
bulk ingestion alone.

## Primary Product Risks

### Source contamination

Assistant-authored claims may be mistaken for user beliefs.

### Scope leakage

A local preference may become a global rule.

### Temporal fossilization

The system may trap the user inside an outdated version of themselves.

### False consensus

Repeated similar chats may look like independent evidence even when they derive
from the same earlier assistant suggestion.

### Self-confirming evaluation

The same model may extract a rule, apply it, and judge itself correct.

### Privacy and manipulation

Conversation-derived personality and decision patterns are sensitive and may
enable targeted persuasion or impersonation.

### Private-core leakage

The intended use of external reasoning can conflict with the requirement that
raw and derived identity never be uploaded. Even small personalized briefs may
reveal identity. The private-core boundary needs an explicit disclosure model
before any provider integration is selected.

### Authority confusion

Predicting what the user might decide does not authorize the system to speak,
sign, publish, purchase, message, or act as that user.

### Marketing overreach

A conceptual cross-agent design may be presented as existing support before
adapters and behavior are verified.

## Working Category Hypothesis

The strongest current category description is:

> **A private subconscious personality core and conscious judgment controller
> for AI agents.**

This is a research hypothesis. Positioning research must test whether
**personal controller**, **judgment model**, **decision persona**, or another
term communicates the product most accurately.
