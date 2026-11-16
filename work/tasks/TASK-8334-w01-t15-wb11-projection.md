---
id: TASK-8334
title: "W-01-T15: WB-11 detail projection"
spec: docs/plan/epics/W-01.md F6
acceptance_criteria: [W-01-T15]
risk_zone: red
status: in-review
branch: w01-t15-wb11-projection
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T15
---

## Objective
WB-11 detail projection.

## Plan (red)
1. `integrations/connect_detail.py`: the merged timeline (newest first, 50 a page, read-time labels, failures not ok) and dependents (from the agents' provider; paused computed from the install's status).
2. `integrations/connect_contract.py`: `GET /v1/integrations/{key}/events` serves the timeline.
3. Tests: `tests/unit/integrations/test_w01t15_detail.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5321). The app imports; the unit file ran green (2 tests). Partial: the detail card route (mode-aware connection card, may-do joined with the write registry, managed-by, linked records through tax: 224 returns) and the client-companies route through `connections.api` with walls still answer 501; the timeline's read-time labels are placeholders until WB-11's handoff wording is copied in (W-01-T16). Gates and
  tests run once at the S47 end pass (build first, test last).
