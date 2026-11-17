---
id: TASK-8407
title: "A-09-T28: Deliverable late sweep and fan-out"
spec: SPEC-658
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
branch: a09-t28-deliverable-late
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T28
---

## Objective
Spec section: docs/plan/epics/A-09.md §3.6 Story 6.3. Deliverable late sweep and fan-out: a Temporal Schedule at 06:00 firm time deriving Late and emitting the late event once, the Today brief Late item, notification fan-out with recipients re-authorised, follow-up drafts as POR-20 template merges (model text only on synthetic tenants under P-25), retention record types.

## Plan (amber)
1. Migration `0945_component_deliverable_late.py` on 0944: `component_deliverables.went_late_at` (stamped once; a return clears it).
2. `assurance/component_late.py`: `ComponentLateSweep` hourly on the batch class; per firm once its local time is 06:00 or later, stamp and emit `component_deliverable.late` once (C16 `component_deliverable_late` to the leads, resolved at delivery); the HOME-02 gate `component_deliverable` (send band, engagement partner) the Today brief lists; the firm template `component_deliverable_follow_up` (registered, DB content) drafted from code's values and sent by a person through `send_templated`.
3. Routes `GET`/`POST /v1/component-deliverables/{id}/follow-up`; the upload event is now `component_deliverable.uploaded` (the catalogue's); retention record types `consolidation`, `component_instructions`, `component_deliverable`; gate events in `review/gates.py`; schedules and workflows in `assurance/api.py`.
4. Tests: `tests/unit/assurance/test_a09t28_component_late.py`. Rollback: `alembic downgrade 0944`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5406). Lint and pyright clean; the app imports. Partial: no model-drafted follow-up exists for any tenant (template merge everywhere, which satisfies P-25 for real firms; the synthetic-tenant model variant waits on N-03); the follow-up template's wording is firm content (import via ADM-10); the demo-clock check (Margaret's Today at Tue Dec 1, 2026 8:30 AM) needs the Brightwater Hale seed slices. Gates and tests run once at the S48 end pass (build first, test last).
