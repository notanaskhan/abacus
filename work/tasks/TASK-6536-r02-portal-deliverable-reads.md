---
id: TASK-6536
title: "R-02-T09/T16/T17 finish: POR-09's live deliverable reads, pages, download and approve"
spec: SPEC-646
acceptance_criteria: [AC-1]  # R-02-T17: a, a2, b, c, d and f render from live data
risk_zone: red
status: in-review
branch: s33r-r02-deliverables
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T09
---

## Objective
The portal deliverables routes answer from C10 instead of 501, so POR-09 renders from live data.

## Plan (red)
- `reporting/deliverable_portal.py`: `portal_client_ids` (the clients a person's grants cover),
  `portal_deliverable` (the readable versions through `reader_version`, each with its seen hash
  and allowed actions; approve only on the newest version whose C18 item waits), and
  `approval_target` (the approve route's C18 item, newest version only).
- `portal/deliverables_contract.py`: list, detail, version, page (PNG through evidence's
  serving), download (302 to the 60-second link) and approve (C18 `client_decide` with the
  version's approval kind and item; the same decision POR-08 records) go live; page comments stay
  501 for R-02-T22.
- `reporting/deliverables.py`: the rail's query ordered by a `wi` alias it never joined (it would
  have failed on its first live read); it now orders by work item, then creation.
- Tests: `tests/unit/reporting/test_s33r_portal_deliverables.py`.
Rollback: revert; the routes answer 501 again.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass). Partial: a draft statement reaches the
  rail only when A-06's send-draft publishes it as a C10 version with its approval item (today
  only the release publishes); page comments are R-02-T22.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3136 | POR-09 approves through C18's item on the deliverable version; reads go through C10's reader rule | no |
