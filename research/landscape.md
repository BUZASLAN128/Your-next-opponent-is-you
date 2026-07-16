# Adjacent Landscape and Gap Analysis

> Status: initial sampled landscape
> Last researched: 2026-07-15
> Confidence: medium for the category distinctions, low for any absolute
> novelty claim

## Research Question

Which parts of the proposed judgment-persona controller already exist, and
which combination appears insufficiently addressed by the sampled systems and
papers?

## Category Map

| Area | Typical question | Representative work | Gap relative to this project |
| --- | --- | --- | --- |
| Retrieval-augmented generation | Which prior item is relevant now? | General RAG and profile retrieval | Relevance does not establish user authority, judgment, or policy |
| Graph memory | Who or what is related, and when was it true? | Graphiti, Zep, Mem0 graph memory | Entity and fact relations do not by themselves model acceptance criteria |
| Long-term agent memory | How can an agent retain context beyond its window? | MemGPT | Memory management does not establish a user-specific normative model |
| Personalized generation | How should output adapt to a user profile or history? | LaMP and related methods | Output similarity and preference are weaker than decision prediction |
| Personalized model parameters | Can a model store per-user behavior patterns? | OPPU | Parametric adaptation may lose inspectable provenance and scoped revision |
| Personal digital twins | Can a model use personal history to respond or behave like a person? | PersonalAI and human digital-twin work | Many evaluations emphasize recall, QA, style, or generic behavior simulation |
| Behavioral simulation | Can a model predict a persona's next behavior? | BehaviorChain | The benchmark is relevant, but not a user-owned policy and evidence controller |
| Personalized evaluation | Do users rank model behavior differently? | Personalized Benchmarking | Establishes the need for individual evaluation, not the controller itself |
| Real-user personalization evaluation | Do synthetic users and automated judges miss personal failures? | MyScholarQA | Supports real-user acceptance but addresses a narrower application |
| Cognitive architectures | How can persistent memory, active workspace, attention, goals, metacognition, and action form one functional system? | Systematic review not yet performed | The user's subconscious-conscious model needs source-grounded decomposition and falsifiable tests |
| Autonomous memory consolidation | When may experience change a durable personal model without manual approval? | Systematic review not yet performed | Requires poisoning resistance, protected boundaries, regression gates, versioning, and rollback together |
| This project | What would this user accept here, why, and with what proof? | Working hypothesis | Requires normative memory, source authority, scope, promotion, and outcome evidence together |

## Reviewed Adjacent Work

### Graphiti and Zep

Official Graphiti material describes a temporal context graph built from
conversations, documents, and structured data. Facts preserve time and can be
invalidated when superseded; retrieval combines semantic, textual, and graph
signals.

**Relevant contribution:** temporal relationships, historical validity,
provenance-oriented context, and graph-backed retrieval are close to the
project's memory requirements.

**Remaining gap:** a temporal fact graph does not determine whether a statement
is a user decision, an assistant suggestion, a temporary instruction, a
verified rule, or a rejected proposal.

Sources: [Graphiti official overview](https://www.getzep.com/platform/graphiti/),
[Zep architecture paper](https://arxiv.org/abs/2501.13956)

### Mem0 Graph Memory

Mem0's official documentation describes extracting entities, relationships,
and timestamps from conversation payloads, storing embeddings and graph edges,
and returning graph relations alongside vector-search results.

**Relevant contribution:** practical multi-session memory extraction and
combined semantic and relational context.

**Remaining gap:** entity and relationship extraction does not establish an
evidence hierarchy between user decisions, assistant context, inferred
preferences, and verified outcomes.

Source: [Mem0 Graph Memory](https://docs.mem0.ai/open-source/features/graph-memory)

### MemGPT

MemGPT proposes virtual context management across memory tiers so an LLM can
operate beyond its context window. Its evaluations include long-document
analysis and multi-session chat.

**Relevant contribution:** separates active context from longer-term memory and
demonstrates sustained conversational state.

**Remaining gap:** managing what an agent remembers is different from deriving
and governing a user's decision criteria.

Source: [MemGPT paper](https://arxiv.org/abs/2310.08560)

### LaMP

LaMP introduces multiple tasks for personalized classification and generation,
using user-profile history and retrieval methods to improve personalized
outputs.

**Relevant contribution:** establishes repeatable personalization tasks and
retrieval baselines.

**Remaining gap:** matching a user's likely output or content preference does
not prove that a system understands why the user would accept or reject a plan.

Source: [LaMP, ACL 2024](https://aclanthology.org/2024.acl-long.399/)

### One PEFT Per User

OPPU stores user-specific behavior patterns and preferences in personal
parameter-efficient modules while combining them with retrieved history and
profiles.

**Relevant contribution:** explores user ownership, behavior shifts, and
parametric plus non-parametric personalization.

**Remaining gap:** parametric user knowledge may be difficult to inspect,
attribute, selectively revoke, or constrain by repository and task scope.
Those concerns require direct evaluation rather than assumption.

Source: [OPPU, EMNLP 2024](https://aclanthology.org/2024.emnlp-main.372/)

### PersonalAI

PersonalAI proposes external personal memory in graph form and includes
temporal and contradictory dialogue information. Its reported experiments
focus on question answering and knowledge extraction benchmarks.

**Relevant contribution:** directly connects graph memory, user history,
temporal change, contradiction, and digital-twin language.

**Remaining gap:** the reported evaluation does not establish a
provenance-preserving controller that predicts and governs one real user's
acceptance, correction, and evidence standards.

Source: [PersonalAI paper](https://arxiv.org/abs/2506.17001)

### BehaviorChain

BehaviorChain evaluates persona-based continuous behavior simulation over
behavior sequences. The authors report that current models still struggle to
simulate continuous human behavior accurately.

**Relevant contribution:** moves beyond dialogue style toward behavior
prediction and offers a neighboring evaluation problem.

**Remaining gap:** synthetic persona and behavior-chain accuracy do not replace
a longitudinal, real-user, source-grounded judgment benchmark.

Source: [BehaviorChain paper](https://arxiv.org/abs/2502.14642)

### Personalized Benchmarking

A 2026 study reports that individual Chatbot Arena users' model rankings can
diverge substantially from aggregate rankings. This supports the premise that
an average preference model is not a reliable substitute for an individual's
evaluation.

**Relevant contribution:** quantitative evidence that personal evaluation can
be materially different from aggregate evaluation.

**Remaining gap:** model ranking is only one expression of preference and does
not capture scoped engineering policies, corrections, or proof requirements.

Source: [Personalized Benchmarking, ACL 2026](https://aclanthology.org/2026.findings-acl.31/)

### MyScholarQA

MyScholarQA infers a user's research interests, proposes personalized actions,
and follows user-approved actions. Its real-user study found nuanced errors
that synthetic users and automated judges did not reveal.

**Relevant contribution:** directly supports real-user evaluation and
user-approved intermediate actions.

**Remaining gap:** the application is personalized research assistance rather
than a portable cross-agent judgment controller.

Source: [MyScholarQA, ACL 2026](https://aclanthology.org/2026.acl-long.723/)

### Personality Inference from Chat History

A 2026 study using real ChatGPT histories reports that personality traits can
be inferred above baseline in multiple cases and emphasizes the associated
privacy and manipulation risks.

**Relevant contribution:** demonstrates that conversational histories can
contain latent personal signals.

**Warning:** the project's ability to infer a persona is also a threat model.
The more useful the model becomes, the more sensitive its data and derived
artifacts become.

Source: [Personality inference paper](https://arxiv.org/abs/2604.19785)

## User's Prior Prototype: HiveMind-Actions

The user identified
[HiveMind-Actions](https://github.com/BUZASLAN128/HiveMind-Actions) as an
earlier simple attempt in the same direction and reported that control was
insufficient. Source inspection at `main` commit
`825dba92b39e4004b0fc4f74e674334f8460ea96` found a software-delivery loop
with analyst, coder, and reviewer roles, structured decisions, static shared
rules, numeric acceptance thresholds, and bounded corrections.

**Relevant contribution:** explicit role separation, machine-checkable output
contracts, a reviewer challenge, and bounded iteration are useful controller
patterns.

**Remaining gap:** a static constitution and generic reviewer threshold do not
represent longitudinal user evidence, source authority, contextual scope,
temporal change, personal outcomes, or separate permissions for prediction,
advice, communication, and action. Broad autonomy and no-question directives
also conflict with the current project's abstention and provenance needs.

See the source-grounded
[HiveMind-Actions case study](hivemind-actions-case-study.md). The workflows
were not executed and their public claims were not reproduced.

## Working Gap Hypothesis

The sampled landscape contains most of the required pieces separately:

- long-term and temporal memory;
- graph relations and provenance-like links;
- personalized retrieval and generation;
- per-user parameter adaptation;
- digital-twin and behavior-simulation research;
- individual preference benchmarking;
- real-user personalization evaluation.

The underexplored combination appears to be:

1. strict separation of user decisions from assistant-authored context;
2. normative and metacognitive memory rather than fact recall alone;
3. project, repository, path, task, role, and time scope;
4. evidence-weighted candidate rules with explicit promotion;
5. versioned, inspectable, revocable, and portable user ownership;
6. a controller that challenges other agents rather than replacing them;
7. evaluation against one real user's later decisions and verified outcomes.
8. explicit separation of mirror, advisor, copilot, learner, and authorized
   delegate behavior.
9. one private subconscious core, a bounded conscious workspace, and dynamic
   mission continuity.
10. autonomous consolidation that cannot self-expand authority or leak the
    represented identity.

This is an **Inference with medium confidence**, not proof of global novelty.

## What Would Falsify the Gap Hypothesis

The hypothesis would weaken or fail if a prior system is found that:

- imports longitudinal, multi-tool conversation history;
- separates speaker authority and user decision events;
- derives scoped and temporal normative rules with provenance;
- requires inspectable promotion and supports revision or revocation;
- governs external agents;
- and evaluates against held-out real-user decisions and outcomes.

Finding such work must be documented even if it reduces the project's novelty.

## Search Limitations

The initial pass:

- used public English-language web search;
- prioritized primary papers and official project documentation;
- sampled representative systems rather than exhaustively reviewing all
  repositories and products;
- did not perform patent or trademark research;
- inspected the user-identified HiveMind-Actions source but did not inspect all
  adjacent open-source systems or reproduce reported benchmarks;
- did not test commercial products;
- did not search non-English literature systematically;
- did not establish that any source is safe or suitable infrastructure.
- has not yet systematically reviewed cognitive architectures, functional
  consciousness theories, autonomous memory consolidation, or machine
  self-model research required by the second-round answers.

Therefore the current safe wording is **underexplored in the sampled
landscape**, not **never done before**.
