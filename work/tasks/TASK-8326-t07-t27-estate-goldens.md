---
id: TASK-8326
title: "T-07-T27: ADR-078 independent AC tests and estate goldens for T22 and T23"
spec: docs/plan/epics/T-07.md F12, F13
acceptance_criteria: [T-07-T27]
risk_zone: amber
status: in-review
branch: t07-t27-estate-goldens
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: T-07-T27
---

## Objective
ADR-078 independent AC tests and estate goldens for T22 and T23.

## Plan (amber)
1. `tests/golden/estate/test_t07t27_thornbury_goldens.py` (`ac-test-author: notanaskhan`): tentative tax 345,800 + 40% x 15,700,000; credit on 18,000,000 and no tax; without DSUE 680,000; AVD unavailable; 17,600,000 > 15,000,000 filing required and Illinois required; the 65-day election a person's only. Each golden cites its TXT-04 artboard.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. The file ran green (6 tests). Partial: the draft-K-1-never-in-the-portal, trustee-question-send and L4 values approval tests wait on their services (T-07-T23's read model and package service are partial). Gates and
  tests run once at the S47 end pass (build first, test last).
