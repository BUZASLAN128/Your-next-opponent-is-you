# Research Documentation Contract

## Scope

This file applies to every file under **research/**. It governs research and
documentation only. It is not a product architecture, implementation plan, or
infrastructure specification.

## Purpose

Preserve the complete reasoning trail behind the project so that later
research can be checked, repeated, challenged, and promoted into decisions
without losing provenance. No substantive product insight, user correction,
research result, limitation, or unresolved question may remain only in chat.

## Required Reading

Before adding or changing research material, read:

1. **research/README.md**
2. **research/conversation-record.md**
3. **research/decision-log.md**
4. **research/source-ledger.md**
5. The topic-specific document being changed

If one of these files does not yet exist, create it as part of the same
documentation task and record why it was missing.

## Capture Requirements

For every material conversation or investigation:

1. Record the date and the question or objective.
2. Separate user statements, observed facts, external claims, inferences,
   proposals, and decisions.
3. Preserve source provenance with a direct URL, repository path, or
   conversation reference.
4. Record contrary evidence, limitations, and uncertainty.
5. State what would verify or falsify the claim.
6. Add newly opened questions to **open-questions.md**.
7. Add every consulted external source to **source-ledger.md**, including
   sources that weaken or contradict the working thesis.
8. Add explicit user decisions to **decision-log.md**.
9. Update **README.md** when a document, status, or research track changes.

Summaries may remove repetition but must not remove a distinct claim,
correction, constraint, risk, alternative, or unresolved question.

## Neutral User Record

- Describe user decisions, deferrals, corrections, uncertainty, and open
  questions without judging the user's competence, motives, or risk posture.
- Do not write that the user "did not understand," "accepted the risk," or
  "refused" something when the evidence only shows delegation, deferral, a
  scope boundary, or a correction request.
- Attribute failed extraction, interpretation, authorization order, or
  implementation behavior to the model, protocol, assistant, or system that
  produced it. Do not transfer those failures to the user.
- Preserve negative scientific evidence and historical mistakes, including
  assistant mistakes, in neutral and precise language. A later approval must
  not rewrite an earlier unauthorized action as pre-authorized.
- Use private quotations only when they are essential, explicitly authorized,
  and safe for the public record. Otherwise record the decision and provenance
  without personal commentary or raw identity-bearing language.

## Research Report Intake and Convergence

For every user-supplied or externally generated research report:

1. Preserve the supplied artifact under **incoming-reports/** with its intake
   date, content hash, provenance, and explicit **Authority: none** label.
2. Separate source-backed observations, source-author claims, local
   inferences, product candidates, and premature prescriptions. A report does
   not become authority because it is detailed, mathematical, or well written.
3. Reconstruct a claim-to-source map for material external claims. Missing
   bibliographies, unresolved citation markers, and unverified named systems
   remain visible evidence gaps.
4. Organize reusable findings in dependency order: data governance, source
   evidence, interpretation schema, consolidation, active context, reasoning,
   authority, evaluation, privacy, and only then implementation candidates.
5. Update **convergence-map.md** so the project moves toward a coherent
   technology-neutral product model without erasing alternatives or promoting
   unconfirmed infrastructure.
6. State what the report strengthens, contradicts, leaves unchanged, and makes
   unsafe to decide. Preserve negative results and transfer limitations.
7. Give the user the next smallest decisions or discriminating checks needed
   to improve the model; do not ask them to choose infrastructure before the
   requirements and evidence are ready.
8. Update the conversation, source, decision, question, and hub records when
   their state changes, then regenerate the combined Markdown bundle.

## Status Vocabulary

Use one of these labels whenever status could be ambiguous:

- **Observed fact:** directly verified in a primary source, repository, or
  runtime.
- **User-reported fact:** stated by the user but not independently verified.
- **Confirmed decision:** explicitly approved by the user and recorded in the
  decision log.
- **Research finding:** supported by cited evidence but not itself a product
  decision.
- **Inference:** a conclusion drawn from evidence; include confidence and what
  could disprove it.
- **Candidate:** an option under consideration.
- **Open question:** unresolved and not safe to assume.
- **Rejected:** explicitly rejected, with the reason and date.
- **Superseded:** formerly applicable but replaced by a later decision.

Silence, repeated discussion, a prototype, an agent recommendation, or an
apparently successful experiment does not count as user approval.

## Evidence Quality

- Prefer primary papers, official documentation, source code, and reproducible
  experiments.
- Label vendor-authored performance claims as vendor claims until reproduced.
- For time-sensitive claims, record the access date and re-check before reuse.
- Do not claim that the project is the first of its kind without a systematic
  literature, product, repository, and patent search whose scope and limits are
  documented.
- Distinguish recall quality, personalization quality, decision prediction,
  behavioral simulation, and verified task outcomes; they are not
  interchangeable evidence.
- Evaluation of a personal model must ultimately include the real user. An
  automated model judge alone cannot close acceptance.

## Infrastructure Decision Gate

- Do not add infrastructure selections, dependency choices, deployment
  topology, storage engines, model providers, or implementation-specific rules
  to this file until the user explicitly confirms them.
- Research documents may compare possible approaches only as **Candidate** or
  **Open question**.
- Every candidate comparison must include alternatives, selection criteria,
  tradeoffs, evidence, and unresolved risks.
- Only an explicit user decision recorded in **decision-log.md** may promote an
  infrastructure candidate to **Confirmed decision**.
- Until that promotion, do not create product dependencies, lockfiles,
  scaffolding, configuration, or operational instructions based on the
  candidate.

## Corpus and Privacy Safety

- Never commit the raw conversation corpus, credentials, tokens, private keys,
  secret-bearing logs, or third-party personal data.
- Record corpus metadata and derived, redacted research artifacts only after
  ownership, consent, retention, deletion, and redaction rules are defined.
- Treat inferred personality, preferences, relationships, vulnerabilities, and
  decision patterns as sensitive personal data.
- Assistant-authored text is context, not user truth. Preserve speaker and
  source attribution through every transformation.
- Derived claims must remain traceable to source evidence and reversible when
  the evidence is corrected or deleted.

## Change Discipline

- Append historical research events; do not rewrite history to match the
  current thesis.
- Mark stale conclusions as **Superseded** and link the replacing evidence.
- Keep raw records, distilled findings, decisions, and proposals in their
  designated documents.
- Do not silently broaden the project from coding-agent governance into
  unrestricted impersonation or autonomous action.
- Do not present a conceptual pipeline as an implemented capability.

## End-of-Conversation Bundle

For every substantive task governed by this file, rebuild the combined
Markdown context before the final response:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/export-all-markdown.ps1
~~~

The script writes
**exports/your-next-opponent-is-you-all-markdown.md**. The generated bundle is
ignored by Git, must not be edited as a source document, and must never replace
the individual files as the authoritative record. Verify that the reported
source count is non-zero and that the generated file excludes itself.

## Completion Checklist

Before finishing a research update, verify:

- Every material conversation point has a durable home.
- Every external factual claim has a source and evidence type.
- Facts, inferences, candidates, and decisions are visibly separated.
- Contradictions and negative findings are preserved.
- New questions and next discriminating checks are recorded.
- No unconfirmed infrastructure choice appears as authority.
- No sensitive raw data or secret has been added.
- All relative links resolve.
- The Git diff contains only the intended research documentation.
- The end-of-conversation Markdown bundle has been regenerated and verified.
