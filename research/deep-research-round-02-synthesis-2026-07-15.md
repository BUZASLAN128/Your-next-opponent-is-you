# Deep-Research Round 2 Synthesis

> Date: 2026-07-15
> Status: research finding and structured intake review
> Input authority: none
> Decision effect: refines the candidate identity ontology and evaluation
> contract; selects no infrastructure, model, schema implementation, threshold,
> or deployment topology

## Research Input

- **Supplied title:** Kişilik çekirdeği için ölçülebilir temel
- **Preserved artifact:**
  [Incoming report](incoming-reports/measurable-personality-core-report-2026-07-15.md)
- **SHA-256:**
  `3280ECD31FDE81CF1484A67825DE9667731AD93CE23BE7746CB740C32ACEEE22`
- **Observed form:** 21,897 bytes, about 2,326 words, and 87 physical lines.
- **Observed citation surface:** zero direct URLs, zero Markdown links, three
  DOI strings, and multiple named works without a bibliography or
  claim-to-source appendix.
- **Declared scope:** the report states that it addresses deep-research
  questions 1, 2, 3, and 8: personality-core definition, conversation
  extraction, consolidation, and persona evaluation.

The report is substantially easier to audit than the preceding one because it
labels findings, inferences, and recommendations and narrows itself to four
research questions. Its claim that direct citations are present is not true of
the supplied attachment surface. A citation interface may have been stripped,
but the missing material cannot be assumed.

## Plain-Language Verdict

This is the strongest report so far for answering **what the personality core
should try to represent** and **how we should test it**. It is not an
architecture and it does not give us a finished formula.

In plain language, it says:

1. A person is not one profile or one writing style.
2. Past conversations are evidence about the person, not the person itself.
3. We should keep what was actually said separate from what an AI infers it
   means.
4. Repeated statements should not enter the durable core automatically.
5. Old and new versions of a person's views must coexist with time and scope.
6. The first real test is whether earlier history predicts later decisions and
   corrections, not whether the system sounds similar.
7. A Mirror that predicts the user and an Advisor that improves the answer are
   different products and must be scored separately.

That direction strongly matches the project. The report becomes unsafe only
when it turns a useful research decomposition into a universal ontology,
schema, or promotion rule.

| Dimension | Assessment | Reason |
| --- | ---: | --- |
| Clarity and research discipline | 8.5/10 | It separates finding, inference, and recommendation and stays mostly technology-neutral |
| Product-direction understanding | 9.0/10 | It focuses on judgment, change, abstention, provenance, and real-user evaluation |
| Primary-source traceability | 5.0/10 | Three DOI strings and accurate named works help, but the delivered artifact still lacks direct links and a claim appendix |
| Claim calibration | 7.0/10 | Most source summaries are directionally accurate; several proposed rules are still presented too naturally |
| Readiness as an ontology | 6.0/10 | It supplies a strong candidate vocabulary that still needs an annotation-agreement test |
| Readiness as architecture | 4.0/10 | No corpus, implementation, benchmark, privacy model, or deployment evidence exists |

The correct disposition is:

> Adopt the report as **Candidate Ontology v0.1 plus an evaluation contract**,
> not as a scientifically proven four-part personality model or an
> implementation design.

## What It Adds Beyond the Previous Report

The preceding report was broad and repeatedly promoted named frameworks. This
report makes four genuine improvements:

- it replaces a fixed nine-category stability hierarchy with connected views
  of traits, values, autobiographical continuity, and metacognition;
- it distinguishes provenance from semantic truth;
- it treats consolidation as evidence independence, scope, time, conflict,
  and attack suspicion rather than recurrence alone;
- it separates judgment fidelity, preference change, calibration, and useful
  advice in evaluation.

The report therefore advances the research model, even though it does not
close the evidence gaps.

## Candidate Identity Ontology

### Source-audited scientific support

The human-science sources support several different views of a person:

- McAdams separates the self as social **actor**, motivated **agent**, and
  autobiographical **author**. Goals and future projects are central to the
  agent view, not automatically outside identity.
- Conway and Pleydell-Pearce distinguish a reconstructive autobiographical
  knowledge base from a goal-sensitive working self.
- Schwartz distinguishes values from traits, beliefs, attitudes, and norms and
  treats values as trans-situational priorities involved in tradeoffs.
- Personality meta-analyses show both relative stability and change across the
  life course. Population-level stability is not an update rule for one user.
- Digital-trace trait inference does not reliably reproduce the psychometric
  properties of questionnaire traits and degrades outside its training domain.

### Correct project interpretation

The most defensible candidate is not four isolated stores. It is four linked
analytical views:

1. **Behavioral patterns or traits:** probabilistic cross-context tendencies,
   never the explanation of every utterance.
2. **Value priorities and conflicts:** what tradeoffs tend to guide judgment,
   with exceptions and scope.
3. **Autobiographical narrative:** how events, life periods, goals, and
   historical selves are connected, while remaining distinct from raw event
   receipts.
4. **Personal metacognitive tendencies:** how the represented user handles
   uncertainty, evidence, questions, correction, and confidence.

Beliefs, preferences, goals, relationships, and skills remain separately
scoped and versioned objects connected to those views. They are not
automatically a disposable outer ring: a goal or relationship can be central
to identity in one period, while a stated value can be temporary or
role-specific.

### Required control-plane split

The report combines two meanings of metacognitive policy:

- **descriptive identity evidence:** the user often asks for proof or tends to
  abstain under uncertainty;
- **protected system control:** the agent must not claim unread evidence or
  execute an irreversible action without authority.

The first may be learned as a source-linked personal tendency. The second is a
product guardrail that learned personality may never rewrite. This split is
mandatory under the existing evidence, identity, and control planes.

## Primary-Source Audit

| Claim or work | Primary source and maturity | What it supports | Transfer limit or correction |
| --- | --- | --- | --- |
| Actor, agent, and author | [McAdams 2013](https://doi.org/10.1177/1745691612464657), peer-reviewed theoretical synthesis | Traits and roles, goals and values, and autobiographical continuity are distinct but connected views of self | It is not a software schema; goals are part of the agent layer, not necessarily outside the core |
| Self-Memory System | [Conway and Pleydell-Pearce 2000](https://doi.org/10.1037/0033-295X.107.2.261), peer-reviewed theoretical model | Autobiographical knowledge has multiple abstraction levels and is reconstructed under current goals | Narrative memory is not an immutable truth store and must remain separate from source receipts |
| Basic human values | [Schwartz 2012](https://doi.org/10.9707/2307-0919.1116), theory author's overview | Values are trans-situational priorities and differ from traits, beliefs, attitudes, and norms | Expressing a value in text does not prove stable adoption or deterministic behavior |
| Trait rank-order stability | [Roberts and DelVecchio 2000](https://pubmed.ncbi.nlm.nih.gov/10668348/), peer-reviewed meta-analysis of 152 longitudinal studies | Relative trait ordering becomes substantially more stable through adulthood | Rank order is a population-relative statistic, not immutability or a single-user promotion threshold |
| Mean-level trait change | [Roberts, Walton, and Viechtbauer 2006](https://pubmed.ncbi.nlm.nih.gov/16435954/), peer-reviewed meta-analysis of 92 samples | Several trait averages continue to change in adulthood | Group-average trajectories do not define an individual's trajectory or fixed decay rate |
| Inferred versus measured traits | [Novikov et al. 2021](https://arxiv.org/abs/2103.09632), preprint reviewing 220 papers | Only 20% reported explicit train/validation/test separation; predicted traits showed weaker temporal and structural properties and poor domain transfer | Supports caution, not the claim that language-derived traits are a reliable core |
| Big Five tests applied to LLMs | [Zierahn et al. 2026](https://arxiv.org/abs/2607.02325), very recent preprint over 244 models | Human Big Five inventories did not recover meaningful model differences or the human five-factor structure | It audits model questionnaires, not human trait inference from a user's conversations |
| Provenance model | [W3C PROV-DM](https://www.w3.org/TR/prov-dm/), W3C Recommendation | Entity, activity, agent, derivation, revision, quotation, primary source, and provenance bundles are established provenance concepts | Provenance describes origin and derivation; it does not prove truth, adoption, or persona membership |
| Conversation-thread context | [Branch-BERT](https://arxiv.org/abs/2211.03061), research paper | Thread context improved the reported target-specific stance task by 10.3 F1 points | The result is from six Hong Kong social platforms against a particular baseline, not a guaranteed gain on personal chats |
| Individual preference rankings | [Personalized Benchmarking](https://aclanthology.org/2026.findings-acl.31/), Findings of ACL 2026 | For 115 active Arena users, individual Bradley-Terry rankings diverged strongly from aggregate ranking | Model-ranking preference is narrower than predicting one person's future decisions |
| Real-user personalization | [MyScholarQA](https://aclanthology.org/2026.acl-long.723/), ACL 2026 | Real users exposed failure types missed by synthetic users and automated judges | It studies personalized scholarly research, not a general virtual self |
| Long-horizon preference change | [HorizonBench](https://arxiv.org/abs/2604.17283), 2026 preprint | In a six-month synthetic benchmark, most tested models struggled to update changed preferences; the best reached 52.8% | The 360 users and their timelines are generated, so results motivate a test but do not validate this user's history |
| Personalized reward evaluation | [Personalized RewardBench](https://arxiv.org/abs/2604.07343), 2026 preprint | It holds general response quality high while varying user-rubric alignment; tested reward models remained imperfect | It evaluates reward models and constructed rubrics, not full persona fidelity or advisor safety |
| Metacognitive monitoring | [Metacognitive Monitoring Battery](https://arxiv.org/abs/2604.15702), 2026 preprint | Accuracy and selective withdrawal can dissociate across 20 frontier models | Generic model self-monitoring is not evidence of the represented user's metacognitive identity |
| Future-event calibration | [KalshiBench](https://arxiv.org/abs/2512.16030), 2025 preprint | Five tested models were systematically overconfident on 300 future-event questions; only one beat the base-rate baseline on Brier skill | It motivates calibration tests but does not measure personal judgment fidelity |
| Sleeper memory poisoning | [Hidden in Memory](https://arxiv.org/abs/2605.15338), 2026 preprint | Poisoned external context can be written, later retrieved, and influence later agent behavior under reported tests | Attack rates depend on the tested systems and do not validate one universal promotion defense |

## Necessary Corrections

### User-authored assertion is not yet a user belief

`speaker_authored=user + claim_holder=user + stance=assert` is a strong
single-event candidate, not proof of durable adoption. Role-play, irony,
debate, testing, coerced answers, past views, temporary instructions, and
missed quotations can still satisfy those fields.

The model therefore needs a separate, initially unknown adoption status plus
scope, time, communicative function, and later support. The same segment may
carry more than one communicative function or more than one represented belief
holder.

### Provenance is not truth

W3C PROV strongly supports separating raw events from derived claims and
tracking revision, quotation, and derivation. It does not make an extracted
claim true or prove that it belongs to the user's personality core.

### Immutable cannot mean undeletable

The report calls the source-event layer immutable. The project also requires
deletion, revocation, and derived-data propagation. The correct requirement is
that retained evidence cannot be silently rewritten. Deletion may remove
protected content while preserving a non-sensitive tombstone and derivation
repair record, subject to the future governance design.

### Promotion is not a universal E0-E3 ladder

The conjunctive promotion formula is a useful gate checklist. The E0-E3 labels
and the rule that only E2 or E3 may become core candidates are local
recommendations, not research findings.

- One explicit user declaration can be sufficient to create an immediately
  active scoped preference or prohibition.
- Repeated behavior may be weak, ambiguous, or caused by one copied source.
- An outcome can contradict a plan without proving the person's value.
- Factual truth, personal preference, identity narrative, and protected policy
  require different evidence.

No universal evidence count or fixed promotion threshold is accepted.

### Blind imitation is not the main target

Asking judges to identify which text was written by the user may reward style
imitation. The primary test remains hidden future judgment: decision, reason,
evidence demand, scope, update, and abstention. Blind user comparison is useful
only when it compares decision quality and personal fit without revealing the
system, not when it rewards deceptive authorship imitation.

## Evaluation Contract Refined

The report strengthens a minimum four-axis evaluation:

1. **Judgment fidelity:** predict what the user will accept, reject, correct,
   defer, or ask and why.
2. **Temporal updating:** use the current scoped view after a correction or
   preference change while retaining historical evidence.
3. **Epistemic discipline:** calibrate confidence, abstain, and ask when the
   user's likely view is not supported.
4. **Useful divergence:** in Advisor mode, improve the proposal while naming
   where and why the advice differs from the predicted user answer.

The first experiment remains Mirror-only. Advisor uplift, automatic
consolidation, and authority should not contaminate the initial judgment test.

The following remain catastrophic gates regardless of average score:

- claiming an unread source was read;
- attributing assistant or third-party text to the user;
- applying another person's or another scope's memory;
- presenting an obsolete preference as current without conflict disclosure;
- inventing a user decision or observed outcome;
- treating persona confidence as action permission.

## Resulting Working Formula

The closest defensible formula is functional, not numeric:

~~~text
predicted_user_judgment = resolve(
    source-grounded_current_context,
    scoped_behavioral_patterns,
    value_priorities_and_conflicts,
    autobiographical_and_temporal_continuity,
    personal_metacognitive_tendencies,
    current_beliefs_preferences_goals_relationships_and_skills,
    contradictions_and_unknowns
)

advisor_output = improve(predicted_user_judgment, general_reasoning)
                 + declared_disagreement
                 + calibrated_uncertainty

permitted_effects = separate_explicit_authority_lease
~~~

This formula organizes the research. It is not a scoring equation, database
schema, prompt, or implementation selection.

## Convergence Effect

The report strengthens:

- a multi-view identity model rather than one flat persona;
- temporal and scoped identity rather than permanent category labels;
- provenance-aware claim extraction;
- evidence independence and poisoning-aware consolidation;
- Mirror versus Advisor separation;
- real-user, temporal, change-aware, and abstention-aware evaluation.

It weakens confidence in:

- traits as the strongest or primary core representation;
- one utterance classifier as a belief detector;
- a universal minimum schema;
- one fixed promotion ladder for every identity object;
- automated judges or style imitation as acceptance evidence.

It leaves unchanged:

- the private corpus boundary;
- the evidence, interpretation, and protected-control separation;
- the local-first requirement;
- the need to begin with annotation and a Mirror-only benchmark;
- the prohibition on infrastructure selection.

## Guidance for the Research Owner

Continue sending the remaining reports unchanged. They should be treated as
different witnesses contributing to one model, not as competing complete
architectures.

After the report batch, the next concrete artifact should be an operational
glossary for a small annotation trial. The glossary should define observable
labels for source event, claim holder, stance, adoption, decision, reason,
scope, correction, supersession, value conflict, metacognitive tendency, and
unknown. It must include ambiguous examples and a rule for removing labels
that humans cannot apply consistently.

Only after that trial should the project decide whether the four analytical
views predict later user judgment better than raw retrieval or a static
summary. That evidence, not the elegance of this report, determines what the
core should contain.

## Decision Effect

No product decision is added or changed. The report refines research
candidates under D-024 and remains subordinate to the infrastructure gate in
D-005.

## Remaining Uncertainty

- The report's original research interface may have displayed citations that
  were not included in the attachment.
- Several 2026 works are recent preprints and have not been independently
  reproduced.
- The primary-source audit confirms major claims and transfer limits but does
  not reproduce any benchmark.
- No real corpus, annotation agreement study, privacy assessment, or runtime
  exists.
- The candidate ontology may still omit, merge, or misclassify important
  dimensions of this user's judgment.
