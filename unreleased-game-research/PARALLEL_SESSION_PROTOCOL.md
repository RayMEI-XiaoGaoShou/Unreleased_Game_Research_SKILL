# Parallel Session Development Protocol

## 1. Goal

Develop the `unreleased-game-research` skill in parallel across multiple OpenCode sessions without breaking shared contracts, duplicating logic, or creating incompatible outputs.

This protocol exists because sessions do not reliably share conversation memory. The shared source of truth must live in files.

## 2. Shared Memory Model

Treat the following as the only reliable shared memory across sessions:

- `unreleased-game-research/PARALLEL_SESSION_PROTOCOL.md`
- `unreleased-game-research/SESSION_STATUS.md`
- `unreleased-game-research/SKILL.md`
- `unreleased-game-research/references/report_schema.md`
- `unreleased-game-research/references/source_reliability.md`
- `unreleased-game-research/references/bias_control.md`

Do not assume another session has seen your chat history.
Do assume another session can read the same files you update.

## 3. Session Layout

Use four working sessions by default.

### Session A

Owns Section 1 and Section 2.

Primary scope:

- public intel
- official video comments
- Section 2 collection and analysis pipeline

Primary files:

- `unreleased-game-research/references/section_1_public_intel.md`
- `unreleased-game-research/references/section_2_official_video_comments.md`
- `unreleased-game-research/scripts/collect_youtube_comments.py`
- `unreleased-game-research/scripts/normalize_text.py`
- `unreleased-game-research/scripts/classify_sentiment.py`
- `unreleased-game-research/scripts/cluster_topics.py`
- `unreleased-game-research/scripts/build_charts.py`
- `unreleased-game-research/scripts/finalize_section_2.py`
- `unreleased-game-research/scripts/run_section_2.py`

### Session B

Owns Section 3.

Primary scope:

- homepage player reviews
- reservation page reviews
- long-review analysis

Primary files:

- `unreleased-game-research/references/section_3_homepage_reviews.md`
- `unreleased-game-research/scripts/*section_3*`
- Section 3-only templates and assets

### Session C

Owns Section 4.

Primary scope:

- creator review videos
- transcript handling
- creator credibility analysis

Primary files:

- `unreleased-game-research/references/section_4_creator_reviews.md`
- `unreleased-game-research/scripts/*section_4*`
- Section 4-only templates and assets

### Session D

Owns integration.

Primary scope:

- shared runners
- shared export logic
- shared UX improvements
- final synthesis and report assembly
- final `SKILL.md` polish

Primary files:

- `unreleased-game-research/SKILL.md`
- shared `references/*.md`
- shared `scripts/*.py`
- export and packaging logic

## 4. Frozen Shared Contracts

The following are frozen by default and must not be changed casually:

- project directory structure
- section folder names
- CSV column names
- findings section order
- step names used by runners
- naming rules for `source_id`, `evidence_id`, and output files

The current frozen contract is defined by:

- `unreleased-game-research/references/report_schema.md`
- `unreleased-game-research/references/source_reliability.md`
- `unreleased-game-research/references/bias_control.md`

## 5. Contract Change Rule

If a session believes a frozen contract must change:

1. Update `unreleased-game-research/SESSION_STATUS.md`
2. Add a `CONTRACT CHANGE REQUEST`
3. Explain:
   - what must change
   - why the current contract is insufficient
   - which files are affected
   - whether the change is breaking or non-breaking
4. Do not silently change shared contract files unless the integration session accepts the change

## 6. File Ownership Rule

A session must not modify files owned by another session unless one of these is true:

- the file is explicitly listed as a shared integration file
- the change is pre-recorded in `SESSION_STATUS.md`
- the integration session requested the edit

Default rule: stay inside your owned scope.

## 7. Shared File Rule

Only Session D should directly modify shared files by default, including:

- `unreleased-game-research/SKILL.md`
- `unreleased-game-research/references/report_schema.md`
- `unreleased-game-research/references/source_reliability.md`
- `unreleased-game-research/references/bias_control.md`
- shared runner interfaces

Other sessions may propose changes, but should first record them in `SESSION_STATUS.md`.

## 8. Required Start-of-Session Workflow

Before a new session starts coding, it must:

1. Read `unreleased-game-research/PARALLEL_SESSION_PROTOCOL.md`
2. Read `unreleased-game-research/SESSION_STATUS.md`
3. Confirm its session identity and ownership scope
4. List the files it plans to touch
5. Update its block in `SESSION_STATUS.md`
6. Then begin implementation

## 9. Required End-of-Session Workflow

At the end of each work block, the session must update `unreleased-game-research/SESSION_STATUS.md` with:

- files touched
- current progress
- assumptions made
- blockers
- contract changes requested
- whether it is ready for integration

Do not end a session after making changes without leaving a written handoff.

## 10. Verification Rule

Each session verifies its own scope.

Examples:

- Session A verifies Section 1 and Section 2 scripts and outputs
- Session B verifies Section 3 scripts and outputs
- Session C verifies Section 4 scripts and outputs
- Session D verifies cross-section compatibility and final integration

Do not assume local success in one section proves full-system compatibility.

## 11. Integration Rule

Session D performs final integration checks:

- schema compatibility
- consistent runner interfaces
- consistent output paths
- no duplicate logic across sections
- no silent contract drift
- final report/export compatibility

Integration is not complete until Session D verifies shared contracts and end-to-end flow.

## 12. Conflict Resolution Rule

If two sessions need the same shared file:

1. Session-local work stops on that file
2. Record the conflict in `SESSION_STATUS.md`
3. Session D resolves the merge path

Do not race-edit shared files in parallel.

## 13. Bootstrap Prompt Template

Use this when opening a new session.

```text
Read `unreleased-game-research/PARALLEL_SESSION_PROTOCOL.md` and `unreleased-game-research/SESSION_STATUS.md` first.

You are Session <A/B/C/D>.
Your ownership scope is <scope>.
Do not modify files owned by other sessions.
Do not change frozen shared contracts unless you first record a CONTRACT CHANGE REQUEST in `unreleased-game-research/SESSION_STATUS.md`.

Before coding:
1. read the protocol
2. update your session block in SESSION_STATUS.md
3. list files you plan to touch
4. then continue implementation
```

## 14. Practical Usage Notes

- If you want maximum safety, keep Session A, B, and C inside section-local files only.
- Use Session D only after one or more section sessions are ready for integration.
- Prefer file-based handoff over chat-based handoff.
- When in doubt, write the assumption into `SESSION_STATUS.md`.
