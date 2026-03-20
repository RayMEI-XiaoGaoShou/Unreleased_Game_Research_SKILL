# Section 3: Homepage Player Review Analysis

## Purpose

Analyze player reviews and comment threads on official reservation or game homepage platforms.
Focus on comments that likely come from highly engaged players, test participants, genre-core users, or IP fans.

## Why This Section Matters

Homepage review areas often gather a different audience from official PV comment sections.

Common differences:

- more long-form comments
- more explicit evaluation of systems and progression
- more test-player hands-on feedback
- stronger genre or IP context
- stronger expectation mismatch analysis

## Inputs

Possible inputs include TapTap game page reviews, Bilibili game detail page comments, official reservation-page long reviews, and other public review pages tied directly to the game's pre-release listing.

## Required Outputs

This section must produce:

- `section_3_homepage_reviews/findings.md`
- `section_3_homepage_reviews/evidence_table.csv`
- `section_3_homepage_reviews/review_registry.csv`
- `section_3_homepage_reviews/review_sample.csv`
- `section_3_homepage_reviews/reviewer_tags.csv`
- `section_3_homepage_reviews/sentiment_summary.csv`
- `section_3_homepage_reviews/topic_summary.csv`

## Core Questions

Answer all of the following when evidence exists:

1. What is the overall sentiment structure of homepage reviews?
2. Which views seem to come from actual test participants?
3. Which views seem to come from genre-core players or IP-core fans?
4. What strengths are repeatedly recognized across detailed reviews?
5. What concerns are repeatedly raised across detailed reviews?
6. Which concerns sound like firsthand experience, and which sound like expectation or projection?
7. How do homepage-review signals differ from official video comment signals?

## Review Selection Rules

A review is high-value when one or more are true:

- it is long-form and concrete
- it references actual play experience
- it compares this game to genre benchmarks
- it discusses systems, loops, onboarding, monetization, optimization, or retention
- it explains why a feature works or fails
- it has strong community resonance through likes or replies
- it reveals player identity context, such as IP fan or genre veteran

A review is low-value when it is mostly one-line emotion, generic hype, platform war, fan war, repeated meme content, pure wishlist, or obvious spam.

## Reviewer Tagging Framework

Every useful review should be tagged where possible.

Use one or more:

- `test_player`
- `ip_core_fan`
- `genre_core_player`
- `returning_franchise_player`
- `curious_noncore`
- `content_creator`
- `unclear`

These tags are analytical guesses unless explicitly stated by the reviewer.
Do not present them as verified identity.

## Sentiment Framework

Use primary labels:

- positive
- neutral
- negative

Optional secondary labels:

- hopeful
- disappointed
- cautious
- nostalgic
- skeptical
- trust-lost
- trust-recovering

## Topic Framework

Use the following stable high-level topics where possible:

- combat and feel
- exploration and world interaction
- collection and progression
- onboarding and UX
- technical quality / optimization
- art / atmosphere / identity
- IP adaptation / franchise faithfulness
- content depth / endgame concern
- monetization anxiety
- pacing and retention
- multiplayer / social potential
- genre competitiveness

## Experience vs Expectation Split

This is mandatory.

For each major point, decide whether it is mainly:

- `firsthand_experience`
- `secondhand_expectation`
- `nostalgia_projection`
- `genre_assumption`
- `mixed`

## Required Tables

### `review_registry.csv`

Columns:

- `review_id`
- `platform`
- `url`
- `game_page_title`
- `review_publish_time`
- `review_length_bucket`
- `likes`
- `replies`
- `capture_method`
- `language`
- `is_longform`
- `notes`

### `review_sample.csv`

Columns:

- `review_id`
- `platform`
- `author_name`
- `text_original`
- `text_normalized`
- `language`
- `likes`
- `replies`
- `sentiment_label`
- `topic_label`
- `experience_basis`
- `is_high_value`
- `confidence_note`

### `reviewer_tags.csv`

Columns:

- `review_id`
- `reviewer_tag`
- `tag_basis`
- `confidence_level`
- `notes`

### `sentiment_summary.csv`

Columns:

- `platform`
- `positive_count`
- `neutral_count`
- `negative_count`
- `positive_ratio`
- `neutral_ratio`
- `negative_ratio`
- `longform_share`
- `experience_based_share`
- `notes`

### `topic_summary.csv`

Columns:

- `topic_label`
- `mention_count`
- `mention_ratio`
- `positive_ratio_within_topic`
- `negative_ratio_within_topic`
- `experience_based_ratio`
- `representative_evidence_id`

## Findings Structure

`findings.md` must include:

- `## Scope`
- `## Core Conclusions`
- `## Reviewer Composition Read`
- `## Overall Sentiment`
- `## High-Value Long Reviews`
- `## Experience-Based Feedback`
- `## Expectation-Driven Feedback`
- `## Topic-Level Strengths and Weaknesses`
- `## Comparison to Official Video Comments`
- `## Confidence and Limitations`
- `## Open Questions`

## Bias Control for Section 3

Be especially careful with IP nostalgia, excellent long reviews being mistaken for consensus, players claiming test experience without enough detail, negative spirals caused by expectation mismatch, positive overprotection from core fans, and platform culture shaping tone.

## Cross-Section Interpretation Rules

Use this section to validate or challenge Section 2.

## Forbidden Moves

- Do not present inferred reviewer identity as verified fact.
- Do not treat reservation-page reviews as representative of all future players.
- Do not mix firsthand test feedback with pure speculation without labeling the difference.
- Do not rank review quality by likes alone.
