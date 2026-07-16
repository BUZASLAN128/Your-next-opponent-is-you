# Original Product and README Proposal

> Source: user-supplied attachment **pasted-text.txt**
> Received: 2026-07-15
> Status: preserved research input, not a set of automatically confirmed
> decisions
> Preservation note: wording is retained; Markdown fences were normalized so
> the document renders correctly.

Repo slug'ını **your-next-opponent-is-you**, README başlığını ise noktalı ve
cümle biçiminde kullanırdım:

# Your Next Opponent Is You.

> **It doesn't learn to talk like you. It learns to judge like you.**

Bunun altına koyacağım ana açılış metni şu:

# Your Next Opponent Is You.

> **It doesn't learn to talk like you. It learns to judge like you.**

An open-source, IDE-agnostic personal controller for AI coding agents.

Your conversations with AI contain more than prompts.<br>
They contain decisions: what you accept, what you reject, what you correct,
what you repeat, and what you require evidence for.

Your Next Opponent Is You turns those decisions into structured, scoped,
and versioned memory.

AI responses are context. **Your decisions are the signal.**

The controller uses that memory to brief, route, challenge, review, and verify
the AI agents you already use—across any IDE.

**Your decisions become memory.<br>
Your corrections become policy.<br>
Your standards become the controller.**

Bence bu açılış ürünün ne olduğunu doğru anlatıyor ve en önemli ayrımı hemen
yapıyor:

AI'ın söylediklerini doğru cevap olarak öğrenmiyor. Kullanıcının AI'a verdiği
tepkilerden karar modelini çıkarıyor.

Hemen altına “core loop”:

## The Core Loop

~~~text
Conversations
    ↓
Decisions and corrections
    ↓
Structured personal memory
    ↓
Policies, preferences, and reusable skills
    ↓
Controller
    ↓
AI agents
    ↓
Independent verification
    ↓
Better decisions
~~~

Biraz daha vurucu sürümü:

~~~md
Every correction becomes evidence.<br>
Every repeated preference becomes a policy candidate.<br>
Every verified solution becomes a reusable skill.<br>
Every failure becomes a guardrail.
~~~

Buradaki “policy candidate” ifadesini özellikle korurdum. Sistem her kullanıcı
cümlesini otomatik olarak kalıcı kanun hâline getirmemeli.

## What It Does

- Imports conversations from different AI assistants and development tools.
- Separates user-authored decisions from assistant-generated context.
- Detects approvals, rejections, corrections, preferences, and guardrails.
- Builds memory scoped by user, project, repository, path, and task type.
- Reviews plans and patches according to the user's accumulated standards.
- Routes work to external coding agents through IDE and agent adapters.
- Converts repeated corrections into inspectable policy and skill candidates.
- Evaluates new behavior through replay, shadow mode, and verification.

Burada “all IDEs supported” diye ilk günden kesin vaat vermek yerine **IDE and
agent adapters** demek daha doğru. Mimari hedefini gösteriyor fakat henüz
yazılmamış entegrasyonları varmış gibi sunmuyor.

## What It Is Not

Bu bölüm ürünün anlaşılmasını ciddi şekilde kolaylaştırır:

This is not a chatbot clone.

It is not designed to imitate your tone, vocabulary, or personality for its
own sake. It is designed to model how you evaluate decisions.

It is not a transcript search wrapper.

It does not treat every past message as equally authoritative. Memories carry
scope, provenance, confidence, time, and revision history.

It is not unchecked autonomous self-improvement.

The system may propose new rules, skills, and strategies, but durable changes
must be evaluated, versioned, and reversible.

Özellikle şu üç ayrım projenin omurgası olur:

- Not voice cloning.
- Not transcript dumping.
- Not uncontrolled self-modification.

## Why the Name?

The next opponent of an AI agent is not necessarily another model.

It is the accumulated record of the person who taught the system what good
work looks like—what they question, what they reject, what they approve, and
what they demand proof for.

Before an agent's plan reaches you, it should first survive your learned
judgment.

**Your next opponent is you.**

Bu bölüm ismi gimmick olmaktan çıkarıp doğrudan ürün mimarisine bağlıyor.

## Principles

### Judgment over imitation

Learn how the user evaluates work, not merely how the user sounds.

### User decisions are the signal

Assistant messages provide context. Approval, rejection, correction, and
verified outcomes provide the learning signal.

### Memory must be scoped

A preference valid for one repository, language, company, or task must not
silently become a universal rule.

### Memory must have provenance

Every durable rule should be traceable to the conversations, decisions, and
outcomes that support it.

### Evidence before confidence

A confident agent response is not proof. Tests, runtime behavior, user
decisions, and verified outcomes carry different evidentiary weight.

### No silent constitutional changes

The controller may propose changes to its policies, but high-impact rules must
be inspectable, versioned, evaluated, and reversible.

### Agent and IDE independence

The user's memory should belong to the user—not to a single model, provider,
IDE, or coding assistant.

Son madde public proje için çok önemli. Ürünün güçlü anlatısı şu olabilir:

Kullanıcının hafızası Cursor'a, Claude'a, Codex'e, Copilot'a veya belirli bir
IDE'ye ait değildir. Kullanıcıya aittir.

## README'in İlk Ekranında Kısa Sürüm

GitHub'da kullanıcı repo açıldığında ilk ekranda şu kadarını görse bile yeter:

# Your Next Opponent Is You.

> **It doesn't learn to talk like you. It learns to judge like you.**

An open-source, IDE-agnostic personal controller for AI coding agents.

It turns your decisions, corrections, rejections, and verified outcomes into
structured memory—then uses that memory to challenge and guide the agents you
already use.

**AI responses are context. Your decisions are the signal.**

**Your decisions become memory.<br>
Your corrections become policy.<br>
Your standards become the controller.**

Arkasından:

## The Core Loop

Conversations → Decisions → Memory → Controller → Agents → Verification

Bu, hero alanı için en temiz sürüm.

## GitHub Repository Description

Repo açıklaması için:

> A personal controller that learns from your decisions, corrections, and
> standards—then guides and challenges AI coding agents across any IDE.

Daha kısa alternatif:

> Turn your AI conversations into memory, policy, and a personal controller for
> coding agents.

Daha vurucu alternatif:

> The controller trained by your decisions—not by the assistants answering you.

Ben ilkini seçerdim; ürünün ne olduğunu en anlaşılır biçimde söylüyor.

## Social Preview / Banner Metni

YOUR NEXT OPPONENT IS YOU.

It doesn't learn to talk like you.<br>
It learns to judge like you.

Altına küçük şekilde:

Personal memory and governance for AI coding agents.

## Manifesto Cümlesi

README'in ilerisine şu parçayı koyabilirsin:

## The Premise

You have already trained a personal engineering model.

It exists across thousands of corrections, rejected proposals, accepted
solutions, architectural decisions, test expectations, and repeated
conversations with AI.

The problem is that this model is fragmented across chat histories and locked
inside individual tools.

This project turns that history into an explicit, portable, and inspectable
controller that belongs to you.

Bu paragraf projenin “neden şimdi?” sorusuna cevap veriyor.

Senin mevcut AGENTS yaklaşımında da ayrı kaynaklar tek bir operasyon
sözleşmesine dönüştürülüyor; yeni projenin özündeki genelleme, benzer şekilde
dağınık kullanıcı kararlarını kaynakları ve kapsamları korunarak kişisel bir
kontrol katmanına çevirmek.

## Benim Seçtiğim Nihai Kombinasyon

### Başlık

Your Next Opponent Is You.

### Ana slogan

It doesn't learn to talk like you. It learns to judge like you.

### Ürün tanımı

An open-source, IDE-agnostic personal controller for AI coding agents.

### Temel ayrım

AI responses are context. Your decisions are the signal.

### Üçlü kapanış

Your decisions become memory.<br>
Your corrections become policy.<br>
Your standards become the controller.

Bu beş cümle markanın neredeyse bütün dilini taşıyabilir. Özellikle “It
doesn't learn to talk like you. It learns to judge like you.” bence projenin
imza cümlesi olmalı.
