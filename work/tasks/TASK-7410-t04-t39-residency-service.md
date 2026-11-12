---
id: TASK-7410
title: "T-04-T39: Residency and state allocation service: facts with citations, option set and conflict rules in code, confirmation as an SHL-10 proposal, client question via issue.send_to_client, allocation read model and xlsx export"
spec: SPEC-649
acceptance_criteria: [AC-8]  # AC-8.1 to AC-8.4, AC-8.6
risk_zone: amber
status: in-review
branch: s38-t04-t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T39
---

## Objective
Confirming full-year NY State and NYC resolves the review point as Samuel, the allocation foots to
598,030, 615,605 and 307,900 with credit min(11,279, 15,920) = 11,279, and the agent principal
cannot confirm or send.

## Plan (amber)
- `tax/residency_service.py`: `OPTIONS` (code; IT-360.1, IT-203 added by the part-year options),
  `facts_from_sources` (organizer, deed, co-op statement, W-2 box 20, 1099 address; each fact cites
  its sources), `residency_inputs` → `residency_rules` (recommendation, conflict), `status_of`
  (review point, action required, confirmed), `client_question` (template words, options only),
  `open_residency` (idempotent per return and scope; insert-only facts), `residency_view`,
  `confirm_approved` (the applier's: `residency.confirm` for the approver; the DB binds a confirmed
  row to its person and proposal), `ResidencyConfirmed` and `on_residency_confirmed` (activates the
  option's worksheet, records `tax_return.engine_reimport_needed`), `allocate_from` /
  `allocation_view` / `allocation_xlsx` (code's sums from `ALLOCATION_FIELDS`).
- `worksheet_review.apply_residency_proposal` confirms after linking; `tax.api` subscribes
  `residency_determination.confirmed`.
- Routes (additive models): `GET …/residency` and `GET …/state-allocation` live, new
  `GET …/state-allocation.xlsx` (`export.create`, fresh MFA).
- Tests: `tests/unit/tax/test_t04t39_residency_service.py` (9 pass),
  `tests/integration/agent_tests/test_t04t39_residency.py`.
- Rollback: revert; no migration (0761's tables).

## Partial
- The review point resolving ("Issues 3 to 2") and the checkpoint: confirmation records the
  person and the proposal; resolving review's issue and recording the checkpoint from the applier
  needs a system issue and checkpoint path in review (as TASK-7309's K-1 treatments).
- `POST …/residency/proposal-runs` stays 501 until T-04-T38's `residency` mode.
- `ALLOCATION_FIELDS` names the IT-201/IT-225/IT-112-R field keys; the seed's Feld return holds
  only line 20 today, so the allocation reads `missing` there until the worksheets are seeded.
- `make generate` for the additive fields and the xlsx route at the end pass.

## Progress log
- `2026-11-12` — Built (S38). 9 unit tests pass; lint and types clean; integration at the end pass.
