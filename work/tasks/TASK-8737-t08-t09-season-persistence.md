---
id: TASK-8737
title: "T-08-T09: Season manifest persistence, reads, reassign, exclude, export and the tax candidate source"
spec: SPEC-710
acceptance_criteria: [AC-1, AC-2, AC-3, AC-7]
risk_zone: amber
status: in-review
branch: s51p-t08-t09-season-persistence
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T09
---

## Objective
Finish T-08-T09 (TASK-8724): the season opens once and its manifest is built from tax's prior-year returns into cohorts and rows (0960), read with tallies computed on read and walls applied, rows reassigned to eligible people and excluded with a reason while the cohort is a draft, and exported as an injection-safe workbook; ENG-07's routes live behind engagements.season_setup.

## Plan (amber)
1. season_manifest.py: exception codes aligned to the contract and SPEC-710 AC-3 (facts by code; the S51 test mis-modelled them).
2. engagements/season_service.py: register_season_candidates; build_manifest (409 no_candidate_source / cohort_approved; supersedes; inputs hash); manifest/cohort/row reads (walled_from: no row, no count); reassign (active, not walled; If-Match); exclude; export_xlsx (safe_xlsx; audited).
3. tax/season_candidates.py registered from tax api: prior-year returns not on hold, forms, entities, office and team of the prior engagement, segment by forms, signer_missing and binder_ambiguous facts; engagements hold_scope facts carry office_id.
4. season_contract: seasons, manifest, build, cohort rows, row patch, exclude, export live; asks, approval and withdrawal stay with T-08-T12.
5. tests/integration/test_t08t09_season_service.py; the pure test updated.

## Progress log
- `2026-11-19` — Built. Not sourced yet (their owners' facts): a seasonal preparer not started, a bounced contact, offshore consent, walls on an assignee at build time, confirmations, changed continuance facts — such rows read ready; letters and fees default to a renewal with no fee change; binder requests are 0 until the binder source is read; the TY2025 214 · 224 · 241 figure needs the T-08 seed slice. The planner step (asks) follows its capability task: planner_available reads false. Gates and tests run once at the S51 end pass (build first, test last).
