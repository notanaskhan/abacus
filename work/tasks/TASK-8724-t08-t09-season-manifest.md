---
id: TASK-8724
title: "T-08-T09: Season manifest builder: cohorts, exception rules and tallies"
spec: SPEC-710
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t08-t09-season-manifest
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T09
---

## Objective
engagements/season_manifest.py (pure): continuing tax clients' candidates grouped into cohorts by office and segment in a stable order, carried preparer and reviewer, exception rules (consent missing, letter lapsed, client inactive) flagging the rows that need an answer, and the manifest tally (engagements, returns, binders, exceptions). Prospects never enter.

## Plan (amber)
1. engagements/season_manifest.py; tests/unit/engagements/test_t08t09_season_manifest.py.

## Progress log
- `2026-11-19` — Built; tests pass (1). Not built: the candidate source tax registers, persistence into season_manifests/cohorts/rows (0960), reassign/exclude, ask answers and export.xlsx; the TY2025 214 · 224 · 241 figure needs the season seed (T-08 seed slice). Gates and tests run once at the S51 end pass (build first, test last).
