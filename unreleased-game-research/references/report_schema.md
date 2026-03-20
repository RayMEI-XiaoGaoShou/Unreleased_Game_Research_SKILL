# Report Schema

## Purpose

Use this schema to standardize every unreleased-game research run.
All sections must produce auditable artifacts.
Do not skip source provenance, confidence notes, or limitations.

## Project-Level Output Contract

Each project must contain:

- `project.yaml`
- `sources/source_registry.csv`
- `sources/source_notes.md`
- `section_1_public_intel/findings.md`
- `section_2_official_video_comments/findings.md`
- `section_3_homepage_reviews/findings.md`
- `section_4_creator_reviews/findings.md`
- `synthesis/executive_summary.md`
- `synthesis/final_report.md`

## Required Metadata

Every artifact must preserve:

- `game_name`
- `section_id`
- `source_id`
- `platform`
- `language`
- `capture_time`
- `analyst_or_agent`
- `confidence_level`
- `limitations_note`

## Source Registry Schema

File: `sources/source_registry.csv`

Required columns:

- `source_id`
- `section_id`
- `platform`
- `source_type`
- `url`
- `title`
- `author_or_channel`
- `publish_date`
- `language`
- `official_status`
- `reliability_score`
- `bias_risk`
- `access_method`
- `capture_status`
- `notes`

Definitions:

- `section_id`: one of `section_1`, `section_2`, `section_3`, `section_4`, `shared`
- `source_type`: official site, official social post, media article, player review, official video, creator review video, interview, repost, forum thread
- `official_status`: official, semi-official, unofficial
- `reliability_score`: 1-5
- `bias_risk`: low, medium, high
- `access_method`: api, browser, manual, transcript, scrape
- `capture_status`: success, partial, failed, manual_fallback

## Evidence Table Schema

Each section must output an `evidence_table.csv`.

Required columns:

- `evidence_id`
- `source_id`
- `claim_or_observation`
- `evidence_type`
- `quote_original`
- `quote_translated`
- `topic_label`
- `sentiment_label`
- `milestone`
- `strength`
- `risk_note`

Definitions:

- `evidence_type`: fact, player_opinion, creator_opinion, analyst_inference
- `strength`: weak, medium, strong

## Findings Markdown Schema

Each `findings.md` must use exactly this order:

1. `## Scope`
2. `## Core Conclusions`
3. `## What We Know`
4. `## What We Infer`
5. `## Key Evidence`
6. `## Positive Signals`
7. `## Negative Signals / Concerns`
8. `## Disagreements / Mixed Signals`
9. `## Confidence and Limitations`
10. `## Open Questions`

### Writing Rules

- Separate observed fact from interpretation.
- Every major conclusion must map to at least one `source_id` or `evidence_id`.
- If evidence is weak, say so explicitly.
- If a source is likely promotional or commercially motivated, label it.
- If translation may distort meaning, preserve original quote.

## Executive Summary Schema

File: `synthesis/executive_summary.md`

Required sections:

1. `## Overall Judgment`
2. `## Product Positioning`
3. `## Market Signal`
4. `## Community Sentiment`
5. `## Core Strengths`
6. `## Major Risks`
7. `## Confidence Level`
8. `## What Needs Further Verification`

## Final Report Schema

File: `synthesis/final_report.md`

Required order:

1. Title
2. Research scope and date
3. Executive summary
4. Section 1 findings
5. Section 2 findings
6. Section 3 findings
7. Section 4 findings
8. Cross-section synthesis
9. Risk register
10. Confidence statement
11. Appendix: source registry summary

## Confidence Scale

Use one of:

- `High`: multiple independent, credible sources align
- `Medium`: some credible evidence exists, but coverage is incomplete
- `Low`: evidence is sparse, highly biased, or inferred from weak signals

## Forbidden Shortcuts

- Do not merge all sentiment into a single number without context.
- Do not present creator opinions as confirmed product facts.
- Do not present official messaging as neutral evidence.
- Do not omit failed capture attempts if they materially affected coverage.
