# HiveMind-Actions Prior Prototype Case Study

> Status: source and documentation inspection
> Reviewed repository state: `main` at
> `825dba92b39e4004b0fc4f74e674334f8460ea96`
> Review date: 2026-07-15
> Evidence tier: source inspection only; workflows were not executed

## Why This Repository Matters

The user identified
[BUZASLAN128/HiveMind-Actions](https://github.com/BUZASLAN128/HiveMind-Actions)
as an earlier, simpler attempt related to the present idea and said that they
did not have enough control over it. It is therefore useful as prior product
evidence, not merely as unrelated prior art.

The repository implements a bounded multi-role software workflow. It does not
implement the longitudinal, source-grounded personal mind described for this
project.

## Observed Workflow

The documented main path is:

~~~text
Issue
  -> Analyst
  -> Coder
  -> Pull request
  -> Reviewer
  -> Approval or bounded correction loop
~~~

The inspected source and configuration also show that:

- a static rules document is inserted into analyst and reviewer prompts;
- analyst and reviewer results use structured response contracts;
- the analyst contract includes a `should_proceed` decision and treats a
  missing value as false;
- research mode can override a negative analyst decision and force work to
  proceed;
- reviewer approval uses configurable numeric thresholds and issue counts;
- reviewer retries and the workflow correction loop are bounded at five;
- security-related reviewer output can reject the result.

## Source Map

- [Repository README](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/README.md)
  describes the roles and workflow.
- [Swarm rules](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/.github/swarm_rules.md)
  provide the shared static constitution.
- [Analyst prompt](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/.github/prompts/swarm_analyzer.prompt)
  and
  [reviewer prompt](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/.github/prompts/swarm_reviewer.prompt)
  define role contracts.
- [Configuration](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/.github/config.json)
  defines reviewer thresholds and retry limits.
- [Analyst source](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/.github/scripts/swarm_analyzer.py)
  and
  [reviewer source](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/.github/scripts/swarm_reviewer.py)
  implement the structured decisions.
- [Reviewer workflow](https://github.com/BUZASLAN128/HiveMind-Actions/blob/main/.github/workflows/agent-reviewer.yml)
  implements the correction loop.

## What Should Be Carried Forward

These are useful design requirements, not selected implementation components:

1. Separate proposal, execution, and critical-review roles.
2. Use explicit, machine-checkable response contracts.
3. Challenge work through a distinct reviewer rather than accepting the
   producing agent's self-assessment.
4. Bound correction loops and expose their state.
5. Retain a human fallback when evidence or confidence is insufficient.

## Why Control Was Limited

The source inspection suggests several structural causes for the user's
experience:

### A flat constitution is not a persona

The shared rules file is a single static instruction layer. It does not model
which user rule applies to which project, task, role, risk, audience, or point
in time. It also has no source trail from a rule back to the user's decisions
and outcomes.

### Generic thresholds replace personal judgment

Numeric review thresholds and issue counts make the loop deterministic, but
they do not establish that the accepted result matches this user's judgment.
There is no longitudinal personal benchmark or user-specific evidence model.

### Autonomy rules conflict with uncertainty handling

The rules include broad directives such as maximum autonomy, never stopping,
and not asking questions except around data loss. Those directives conflict
with a system that must abstain when it has not read a source, lacks authority,
or cannot resolve contradictory evidence.

### Self-correction is not self-knowledge

A bounded retry loop can improve an artifact, but it does not by itself learn
why the user accepted or rejected the result. There is no durable record of
personal decisions, provenance, scope, temporal supersession, or verified
outcomes.

### Review is not independently grounded in the person

The reviewer is a separate role, but it is still grounded mainly in the same
static rules and task flow. It does not compare the work with a personally
validated judgment model or independently sourced user evidence.

### Action authority is too coarse

The flow is designed to keep moving. It does not express separate permissions
for observing, remembering, recommending, drafting, communicating, approving,
and executing as the user.

## Requirements Derived for This Project

The next system should preserve the useful loop mechanics while adding:

- an explicit operating mode for every output;
- a source receipt for every claim that it read or remembered something;
- scope, time, authority, confidence, and outcome on durable personal claims;
- candidate learning rather than silent self-modification;
- verification grounded separately from the producing agent;
- bounded, visible, and auditable correction loops;
- abstention or a question when required evidence is absent;
- explicit permission and an action receipt before communicating externally;
- a portable personality core that is not owned by one agent surface;
- a declared distinction between user-authored bootstrap material and behavior
  inferred from observed history.

These are technology-neutral requirements. No model, database, framework,
runtime, container system, or provider is selected by this case study.

## What This Inspection Does Not Prove

- The workflows were not executed.
- Public claims about success, quality, or autonomy were not reproduced.
- The inspection does not establish that the project is unsafe in every use.
- It does not establish a complete architecture for the new project.
- It does not validate a claim of consciousness or AGI.
- It does not select any HiveMind-Actions component as a dependency.
