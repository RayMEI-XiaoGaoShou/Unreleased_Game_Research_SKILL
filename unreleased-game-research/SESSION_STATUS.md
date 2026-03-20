# Session Status

Use this file as the shared progress board for all parallel sessions.

Update your session block before and after each focused work block.

## Session A

- Owner: Section 1 + Section 2
- Scope: public intel, official video comments, Section 2 runner and analysis pipeline
- Files touched:
  - `unreleased-game-research/references/section_1_public_intel.md`
  - `unreleased-game-research/references/section_2_official_video_comments.md`
  - `unreleased-game-research/scripts/collect_youtube_comments.py`
  - `unreleased-game-research/scripts/collect_bilibili_comments.py`
  - `unreleased-game-research/scripts/normalize_text.py`
  - `unreleased-game-research/scripts/classify_sentiment.py`
  - `unreleased-game-research/scripts/cluster_topics.py`
  - `unreleased-game-research/scripts/build_charts.py`
  - `unreleased-game-research/scripts/finalize_section_2.py`
  - `unreleased-game-research/scripts/run_section_2.py`
  - `unreleased-game-research/references/credentials_guide.md`
- Current status: Section 2 pipeline is fully implemented, locally validated, and supports both YouTube and Bilibili collection. The `run_section_2.py` runner features resume capabilities (`--from-step`, `--skip-collect`), rigorous CSV contract adherence, multi-platform collection logic, and a CSV-based manifest mode for batch processing multiple milestones. Section 1 remains reference-driven as planned (fulfilled natively by AI using websearch based on the SOP). Credentials guide has been created to assist non-technical users.
- Current focus: Work on Section 1 and Section 2 is stable and considered complete for v1.
- Contract changes requested: none
- Blockers: live YouTube/Bilibili API/cookie scraping was not performed due to lacking valid credentials, but all offline paths, fail-fast validations, and empty-set workflows pass end-to-end.
- Assumptions made:
  - Section 2 v1 uses rule-based normalization, sentiment, and topic classification to preserve deterministic behavior before introducing ML complexity.
  - Runner resume behavior is explicit and fail-fast; no automatic recovery.
  - Manifest mode processes all collection tasks sequentially, followed by a single downstream processing pass.
- Ready for integration: yes

## Session B

- Owner: Section 3
- Scope: homepage player reviews, reservation page comments, long-review analysis
- Files touched:
  - `unreleased-game-research/SESSION_STATUS.md`
  - `unreleased-game-research/scripts/capture_taptap_reviews.py`
  - `unreleased-game-research/scripts/section_3_common.py`
  - `unreleased-game-research/scripts/annotate_section_3_reviews.py`
  - `unreleased-game-research/scripts/finalize_section_3.py`
  - `unreleased-game-research/references/section_3_bilibili_semi_auto_guide.md`
  - `unreleased-game-research/scripts/run_section_3.py`
  - `unreleased-game-research/scripts/capture_bilibili_page.py`
- Current status: Section 3 now supports TapTap direct crawl plus a Bilibili semi-automatic request-bundle flow; both the missing-input guidance path and a mock end-to-end Bilibili capture run were validated locally. Bilibili capture now parses cURL bash commands directly (Copy as cURL from DevTools), eliminating the need for manual field extraction—users simply paste the copied cURL text and the parser extracts URLs, Cookie, Referer, and User-Agent automatically
- Current focus: hand off the new Bilibili semi-automatic mode for integration review and decide later whether to add fully automatic browser-assisted collection
- Contract changes requested: none
- Blockers:
  - `scripts/init_project.py` still does not seed Section 3-specific CSVs, so `run_section_3.py` currently bootstraps them at runtime instead of relying on shared project initialization
- Assumptions made:
  - work stays inside Section 3-owned files unless a contract issue must be escalated first
  - manual import of review exports is an acceptable Section 3 fallback when live page capture is unavailable
  - the MVP can prioritize TapTap-style review imports while leaving other page-specific capture scripts for later expansion
- Additional notes:
  - capture now merges by `review_id` instead of overwriting prior Section 3 review rows
  - runner readiness checks now require real data rows, not just seeded headers
  - manual-import source registry entries are marked `manual_fallback`
  - `run_section_3.py` now accepts direct `--page-url` capture instead of requiring `--input-file`
  - TapTap direct review-page capture writes `capture_method=direct_html_fetch` and `access_method=scrape`
  - TapTap app review listing capture now uses the public page-exposed `review/v2/list-by-app` path to import multiple long reviews directly from `app/<id>` or `app/<id>/review`
  - Bilibili Section 3 now accepts a semi-automatic request bundle file containing copied `recommend` or `page` request URLs plus `Cookie` and `Referer`
  - `run_section_3.py` proactively prints the plain-language Bilibili guide when this bundle is missing
  - Bilibili game detail capture no longer stops at static best-effort only; it can normalize real API-shaped comment payloads into Section 3 outputs
- Bilibili capture simplified: instead of manually extracting 5 fields (URL, Cookie, Referer, User-Agent), users now paste cURL bash commands directly; `parse_curl_command()` extracts all needed headers automatically
- heuristic wording now reports direct-use indicators via firsthand-or-mixed experience instead of only exact firsthand matches
- Planned files for this work block:
  - `unreleased-game-research/SESSION_STATUS.md`
  - `unreleased-game-research/scripts/capture_taptap_reviews.py`
  - `unreleased-game-research/scripts/capture_bilibili_page.py`
  - `unreleased-game-research/scripts/section_3_common.py`
  - `unreleased-game-research/scripts/run_section_3.py`
  - `unreleased-game-research/scripts/annotate_section_3_reviews.py`
  - `unreleased-game-research/scripts/finalize_section_3.py`
- Ready for integration: yes

## Session C

- Owner: Section 4
- Scope: creator review videos, transcript pipeline, creator credibility analysis
- Files touched:
  - `unreleased-game-research/SESSION_STATUS.md`
  - `unreleased-game-research/scripts/section_4_common.py`
  - `unreleased-game-research/scripts/import_section_4_candidates.py`
  - `unreleased-game-research/scripts/import_section_4_transcripts.py`
  - `unreleased-game-research/scripts/annotate_section_4_claims.py`
  - `unreleased-game-research/scripts/finalize_section_4.py`
  - `unreleased-game-research/scripts/run_section_4.py`
  - `unreleased-game-research/scripts/extract_video_audio.py`
  - `unreleased-game-research/scripts/transcribe_audio.py`
- Current status: completed and ready for integration. The Section 4 auto-search, shortlist, and transcription pipeline is fully implemented, tested, and ready. The 'auto-search -> shortlist -> manual select -> transcribe -> summarize' flow works end-to-end.
- Current focus: none (Session C tasks completed)
- Contract changes requested: none
- Blockers: none
- Assumptions made:
  - v1 will support manual candidate and transcript import as the primary path
  - automatic video/audio/transcript capture will be best-effort and must not block report generation
  - shared report schema remains frozen; Section 4 findings therefore follow the shared heading order rather than the richer section-specific heading list
- Ready for integration: yes

## Session D

- Owner: integration
- Scope: shared contracts, shared runner interfaces, final synthesis, export and packaging
- Files touched:
  - `unreleased-game-research/SKILL.md`
  - `unreleased-game-research/references/report_schema.md`
  - `unreleased-game-research/references/source_reliability.md`
  - `unreleased-game-research/references/bias_control.md`
  - `unreleased-game-research/PARALLEL_SESSION_PROTOCOL.md`
  - `unreleased-game-research/SESSION_STATUS.md`
- Current status: shared contracts drafted; final integration not started
- Current focus: preserve shared contract stability while Section 3 and Section 4 are developed in parallel
- Contract changes requested: none
- Blockers: waiting for Section 3 and Section 4 implementations to exist
- Assumptions made:
  - shared contracts remain frozen unless explicitly escalated
  - Session D is the default owner for final merge and final `SKILL.md` cleanup
- Ready for integration: not yet

## Contract Change Requests

- none

## Integration Checklist

- [x] Shared contract files created
- [x] Parallel protocol created
- [x] Session status board created
- [x] Section 2 one-click runner created
- [x] Section 3 minimum viable pipeline implemented
- [x] Section 4 minimum viable pipeline implemented
- [ ] Shared export flow validated across all sections
- [ ] Final integration pass completed by Session D
