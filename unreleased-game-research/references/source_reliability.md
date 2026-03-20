# Source Reliability and Bias Rules

## Purpose

Use this guide to score public sources for unreleased-game research.
The goal is not to find perfectly objective sources.
The goal is to make source quality, likely bias, and evidence strength explicit.

## Core Principle

Every source answers three different questions:

1. Can this source tell us what happened?
2. Can this source tell us what people think?
3. Can this source tell us what it means?

Many sources are good at only one of these.

## Mandatory Output Fields

Every source must be labeled with:

- `official_status`
- `source_type`
- `reliability_score`
- `bias_risk`
- `evidence_scope`
- `notes`

### Recommended values

- `reliability_score`: 1-5
- `bias_risk`: low, medium, high
- `evidence_scope`: factual, experiential, interpretive, mixed

## Reliability Score Guide

### 5 - Very Strong

Use when the source is highly reliable for the claim being made.

Typical examples:

- official test notice for test date
- official trailer upload for reveal timing
- direct developer interview for stated design intent
- original full video or full review text, not reposted summary
- firsthand test-player review with detailed concrete observations

### 4 - Strong

Use when the source is credible but not perfect.

Typical examples:

- reputable game media report with direct citations
- creator review with concrete gameplay evidence and transparent stance
- platform review page with clear long-form hands-on feedback
- translated source with verifiable original

### 3 - Mixed

Use when the source is useful but requires caution.

Typical examples:

- general media recap based on official materials
- short user comments with limited detail
- secondhand summary of another article
- creator video with strong opinions but thin evidence
- partial transcript or partial page capture

### 2 - Weak

Use when the source offers only soft signal.

Typical examples:

- reposted rumor
- low-detail emotional comments
- SEO article with little original reporting
- short clips without context
- anonymous claim without supporting evidence

### 1 - Very Weak

Use when the source is unreliable for analytical claims.

Typical examples:

- obvious clickbait aggregation
- unverifiable rumor account
- meme thread with no substantive content
- heavily edited excerpt without original context

## Bias Risk Guide

### Low Bias Risk

Typical for:

- factual official notices about dates or participation rules
- direct source materials with little interpretive layer
- long-form firsthand reviews with concrete evidence and balanced critique

Low bias does not mean complete neutrality.

### Medium Bias Risk

Typical for:

- creator reviews without obvious sponsorship disclosure
- large community comment threads
- game media that may depend on industry access
- translated summaries where nuance may be lost

### High Bias Risk

Typical for:

- promotional preview articles
- sponsored creator content
- official marketing copy used as design evidence
- fandom-dominated comment sections
- anti-fan or console-war style discussion threads
- repost chains that all derive from one primary source

## Source Type Rules

### Official Sources

Examples:

- official site
- official social account
- official trailer
- official interview
- official test announcement

Use for:

- naming
- dates
- announced features
- stated goals
- formal scope

Do not use official sources alone to prove:

- actual gameplay quality
- player satisfaction
- system depth
- optimization quality
- commercial model acceptance

### Media Sources

Examples:

- game news site
- feature story
- preview article
- industry analysis post

Use for:

- discovery of facts and chronology
- quoted interviews
- framing of market context

Risks:

- PR dependence
- copied newswire tone
- shallow rewriting of one primary source

Always try to trace the origin.

### Community Comment Sources

Examples:

- official video comments
- reservation page comments
- forum discussion
- social thread reactions

Use for:

- visible audience sentiment
- recurring concerns
- language of expectation
- comparison references
- emotional triggers

Risks:

- not representative
- fandom concentration
- meme amplification
- brigading
- low-information emotional noise

Use as signal, not proof.

### Test-Player Review Sources

Examples:

- long-form TapTap review
- detailed Bilibili game-page review
- forum hands-on writeup

Use for:

- experiential insight
- friction points
- feature-depth hints
- onboarding, progression, combat, optimization observations

Risks:

- unknown skill level
- unknown test scope
- nostalgia or IP bias
- overgeneralization from one player

These are often high-value but never fully representative.

### Creator Review Video Sources

Examples:

- Bilibili creator review
- YouTube hands-on review
- test feedback video essay

Use for:

- structured gameplay explanation
- repeated pros/cons across creators
- concrete seen footage tied to commentary

Risks:

- sponsorship
- self-brand positioning
- shallow hot-take style
- experience variance
- transcript distortion after ASR

Separate creator claim from confirmed evidence.

## Source Combination Rules

A strong conclusion usually needs at least two of the following to align:

- factual source
- audience reaction source
- experiential source
- creator interpretation source

## Independence Rule

Do not count repeated articles as independent support if they all derive from:

- one press release
- one interview
- one leaked screenshot set
- one original creator video

Trace the source chain whenever possible.

## Translation and Cross-Market Rules

When using translated material:

- preserve original quote when possible
- store translated quote separately
- note if slang, sarcasm, or game jargon may distort meaning
- do not compare translated emotional intensity too literally across languages

## Sponsorship / Incentive Heuristics

Mark higher bias risk when you see signals like:

- explicit paid promotion label
- giveaway or campaign linkage
- access-dependent preview relationship
- unusually one-sided praise with little concrete detail
- creator avoids obvious weaknesses while emphasizing marketing beats

Do not assume all positive content is sponsored.
Do assume incentives may shape framing.

## Confidence Construction Rules

Use source reliability to inform confidence, but do not reduce confidence to score average.
Confidence should consider:

- number of independent sources
- specificity of evidence
- cross-source consistency
- recency
- platform diversity
- capture completeness

## Common Failure Modes

Avoid these:

- treating official language as neutral fact
- treating a large comment count as representative evidence
- treating one excellent long review as broad user consensus
- treating one creator's opinion as market truth
- treating repeated reposts as multiple confirmations

## Minimal Source Requirements by Section

### Section 1

Need at least:

- 1 official source
- 1 contextual source beyond official messaging

### Section 2

Need at least:

- 1 official video source
- accessible comment sample with documented capture method

### Section 3

Need at least:

- review-page source
- at least some comments with concrete experiential detail

### Section 4

Need at least:

- 3 candidate creator videos
- clear reason for selecting final 3-5
- creator credibility note for each selected video

## Reporting Rule

When evidence is weak, say:

- `signal exists but evidence remains limited`
- `likely but not yet well confirmed`
- `highly discussed, but not strongly validated`
- `credible concern, representativeness uncertain`

Do not force certainty where the source base does not support it.
