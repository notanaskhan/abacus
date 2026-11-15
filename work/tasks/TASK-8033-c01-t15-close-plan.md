---
id: TASK-8033
title: "C-01-T15: close plan service — versions, publish, request-publish, templates, pinning"
spec: SPEC-655
acceptance_criteria: [AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-22]
risk_zone: amber
status: in-review
branch: c01-t15-close-plan
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T15
---

## Objective
CLS-09's plan behind the C-01-T04 stubs: one plan per client entity, drafts, row and request
template edits under If-Match, computed tallies, human-only publish with `effective_from`,
request-publish as a HOME-02 gate, history, the template import endpoint and BD1 pinning.

## Plan
1. [x] `closes/plans.py`: `get_plan`, `plan_history`, `create_draft`, `patch_row`, `add_row`,
   `add_request_template`, `publish`, `request_publish`, `adopt` (one or all), `pin_plan`,
   `list_templates`, `import_template`.
2. [x] `closes/gate_sources.py`: C13 source `close_plan_publish` (`final_approval`, read through
   `close_plan.publish`), registered at import; review's `C13_EVENTS` gain
   `close_plan.publish_requested` and `close_plan.published`; `events.py` adds both events.
3. [x] Routes wired (12); `draft-from-history` stays 501 for C-01-T30. Client regenerated.
4. [x] Tests: `tests/integration/test_c01t15_close_plan.py` (AC-14 to AC-19, AC-22).
Rollback: revert; no migration.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built. Tallies are computed from the rows (Manager = manager approval, Senior =
  the rest; requests = client-visible templates). Publishing pins closes past BD1 first
  (DEC-5021), then the trigger refuses unadopted drafted rows (409 `unadopted_rows`). A
  Senior's publish is 403 by the matrix; request publish is idempotent and raises one gate.
  History reads "<person> via Agent · Close Planner" for an agent-drafted version. Not run (end
  pass).
- **Partial.** Adoption records the person on the row; resolving the agent's P-35 suggestion
  lands with C-01-T30's planner mode, which writes the drafted rows. `RequestPublishWorkflow`
  (C-01-T19) calls `pin_plan` at BD1.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5021 | Plan scope by the client's Monthly close engagement; pin past-BD1 closes before publishing; gate read through publish | no |
