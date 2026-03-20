# Section 2: Official Video Comment Sentiment Over Milestones

## Purpose

Analyze how public sentiment changes across official video milestones for an unreleased game.
Focus on official PVs, gameplay demos, test trailers, and milestone showcase videos.
This section measures visible audience reaction to official content at specific moments.

## Why This Section Matters

Different milestones reveal different things:

- reveal PV: theme, world, character, art style, positioning
- gameplay demo: combat, controls, content loop, polish
- test trailer: iteration quality, visible progress, confidence recovery or decline

The key value is not only single-video sentiment.
The key value is change over time.

## Inputs

Possible inputs include official YouTube videos, official Bilibili videos, gameplay showcases, test trailers, livestream replay segments, and official milestone videos embedded on official channels.

## Required Outputs

This section must produce:

- `section_2_official_video_comments/findings.md`
- `section_2_official_video_comments/evidence_table.csv`
- `section_2_official_video_comments/video_registry.csv`
- `section_2_official_video_comments/comment_sample.csv`
- `section_2_official_video_comments/sentiment_summary.csv`
- `section_2_official_video_comments/topic_summary.csv`
- `section_2_official_video_comments/milestone_delta.csv`

## Core Questions

Answer all of the following when evidence exists:

1. What is the overall positive, neutral, and negative distribution at each milestone?
2. Which design topics dominate discussion at each milestone?
3. What are the most representative positive views?
4. What are the main concerns, doubts, or negative views?
5. How does sentiment shift from reveal to later tests?
6. Which changes in official content likely drove those shifts?
7. Which apparent signals are strong, and which may just be noise or fan hype?

## Video Selection Rules

A video is valid for this section only if all are true:

- it is officially published or clearly official-channel distributed
- it corresponds to a recognizable milestone
- the content is materially about the game
- the video has enough comments to extract signal
- the comment section is publicly accessible

## Comment Sampling Rules

Use one of these modes:

- `full_capture`
- `top_plus_recent`
- `stratified_sample`

The chosen mode must be recorded in `video_registry.csv`.

Preserve diversity across highly liked comments, normal comments, early reactions, later reflections, short emotional reactions, and long analytical comments.

## Preprocessing Rules

Before analysis:

- remove duplicates
- mark spam, meme-only, copy-paste, or bot-like content
- preserve original language
- normalize text into a separate field
- preserve likes, replies, publish time
- keep platform identity

Do not overwrite original text.

## Sentiment Framework

Use three primary labels:

- positive
- neutral
- negative

Optional secondary tags:

- excited
- skeptical
- disappointed
- curious
- comparison-driven
- commercialization-anxious
- optimization-concerned

Sentiment is not enough on its own.
Every sentiment result must be interpreted with topic context.

## Topic Framework

Map comments into reusable design dimensions when possible:

- art / visual identity
- character design
- world / setting / atmosphere
- gameplay loop
- combat feel
- exploration
- technical quality / optimization
- UI / readability
- innovation / sameness
- monetization anxiety
- IP fit / nostalgia
- genre comparison
- trust in development progress

## Milestone Delta Analysis

This is mandatory.

For every pair of adjacent milestones, identify:

- what sentiment improved
- what sentiment worsened
- which topics rose in importance
- which concerns disappeared
- which new concerns emerged
- what likely visible content change explains the shift

Do not claim causality unless evidence is strong.

## Required Tables

### `video_registry.csv`

Columns:

- `video_id`
- `milestone_id`
- `platform`
- `url`
- `title`
- `publish_date`
- `channel_name`
- `official_status`
- `content_type`
- `comment_capture_mode`
- `comments_captured`
- `language_mix`
- `notes`

### `comment_sample.csv`

Columns:

- `comment_id`
- `video_id`
- `platform`
- `comment_time`
- `author_name`
- `text_original`
- `text_normalized`
- `language`
- `likes`
- `replies`
- `is_top_comment`
- `is_spam_or_noise`
- `sentiment_label`
- `topic_label`
- `confidence_note`

### `sentiment_summary.csv`

Columns:

- `video_id`
- `milestone_id`
- `positive_count`
- `neutral_count`
- `negative_count`
- `positive_ratio`
- `neutral_ratio`
- `negative_ratio`
- `positive_like_weight`
- `negative_like_weight`
- `notes`

### `topic_summary.csv`

Columns:

- `video_id`
- `milestone_id`
- `topic_label`
- `mention_count`
- `mention_ratio`
- `positive_ratio_within_topic`
- `negative_ratio_within_topic`
- `avg_likes`
- `representative_evidence_id`

### `milestone_delta.csv`

Columns:

- `from_milestone`
- `to_milestone`
- `topic_label`
- `direction`
- `observed_change`
- `likely_driver`
- `confidence_level`
- `supporting_evidence_ids`

## Findings Structure

`findings.md` must include:

- `## Scope`
- `## Core Conclusions`
- `## Milestone Overview`
- `## Overall Sentiment by Milestone`
- `## Topic-Level Sentiment`
- `## Representative Positive Views`
- `## Representative Negative Views / Concerns`
- `## Milestone-to-Milestone Change`
- `## Confidence and Limitations`
- `## Open Questions`

## Platform Comparison Rules

When combining YouTube and Bilibili:

- do not assume same audience composition
- do not compare raw like counts directly across platforms
- prefer ratio and topic comparison over volume comparison
- note culture and language differences in expression style

## Bias Control for Section 2

Be especially careful with hype spikes, fandom concentration, meme comments drowning analytical comments, official traffic boosting, and comparison comments driven by genre war rather than evidence.

## Escalation Rules

Escalate to later sections when comments mention real hands-on experience from test players, recurring concerns require confirmation from homepage reviews, positive or negative views may be driven by creator opinion leaders, or official content does not show enough gameplay to judge the issue.

## Forbidden Moves

- Do not use one video to represent the entire project lifecycle.
- Do not treat like count as a direct proxy for market size.
- Do not collapse topic-specific sentiment into one flat conclusion.
- Do not compare unlike milestones as if they were equivalent artifacts.
