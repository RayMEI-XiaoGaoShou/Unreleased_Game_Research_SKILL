# Research Workflow

## Purpose

Run a full unreleased-game study in a predictable, auditable order.
Use this document when the user wants an end-to-end report rather than a single isolated section.

## Standard Sequence

1. Initialize the project with `scripts/init_project.py`.
2. Create `project.yaml` with game name, aliases, target markets, milestones, and operating mode.
3. Populate `sources/source_registry.csv` with initial seed sources.
4. Run Section 1 to establish product framing and milestone map.
5. Run Section 2 if official milestone videos exist.
6. Run Section 3 if homepage or reservation reviews exist.
7. Run Section 4 for the latest meaningful test phase.
8. Normalize outputs, update evidence tables, and reconcile identifiers.
9. Write `synthesis/executive_summary.md`.
10. Assemble `synthesis/final_report.md`.
11. Export PDF if requested.

## Multi-Agent Handoff Rules

- The coordinator creates folders and seeds `project.yaml`.
- Section agents write only to their own section folders.
- The normalization step may read across sections but must not rewrite raw captures.
- The editor reads section outputs only after section artifacts exist.

## Minimum Deliverable

Even if collection is partial, deliver:

- a populated source registry
- section findings for all attempted sections
- explicit confidence and limitation notes
- a synthesis that preserves unresolved uncertainty

## Failure Handling

If a section cannot be completed:

1. Record capture attempts.
2. Mark what data was missing.
3. Lower confidence.
4. Continue with partial but auditable output.

## Priority Order

If time is limited, prioritize:

1. Section 1
2. Section 3
3. Section 2
4. Section 4

Use this order when the objective is strategic insight rather than broad signal coverage.
