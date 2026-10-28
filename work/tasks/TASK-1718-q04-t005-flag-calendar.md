---
id: TASK-1718
title: Q-04-T005 Flag renewal calendar
spec: SPEC-403
acceptance_criteria: [AC-10]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T005
branch: s14-q04-t005
created: 2026-10-28
updated: 2026-10-28
---

## Objective
No flag expires inside a release window unless both founders recorded why (RK-15): `feature_flags
--check` refuses an `expires` inside any window in `deploy/windows.yaml` without
`window_exception {reason, approved_by}`; `make flag-calendar` lists flag, owner, expiry, last
train before expiry and window conflicts, with a 21-day warning. Acceptance (backlog row): "A flag
expiring Sep 10, 2027 without window_exception fails check-fast and make flag-calendar lists every
registered flag with its last renewal train."

## Plan (amber)
- `abacus_tools/codegen/feature_flags.py`: optional `window_exception` (approved_by a handle that
  is not the owner) and `journeys` (distinct slugs, for Q-04-T010); `window_conflicts`,
  `train_days` (Thursday outside windows, the in-window Tuesday slot while production is in one),
  `flag_calendar`, `calendar_lines`; `--calendar`; the conflict check in `--check`.
- `Makefile` `flag-calendar`; `docs/architecture/feature-flags/_header.yaml` documents the fields.
- Rollback: revert the branch.

## Acceptance
| Check | Test |
|---|---|
| Sep 10, 2027 expiry fails naming autumn-2027; excepted entry passes and is marked; bad exceptions and journeys refused | `backend/tests/unit/tools/test_q04t005_flag_calendar.py` |
| Trains: Thursdays outside windows, Tuesday slots inside a live window | same |
| Every registered flag listed with a last train; 21-day warning; the committed registry passes | same (20 tests) |

## Progress log
- `2026-10-28` — Built. 20 passed; SPEC-011 flags suites (29) still pass; `make flag-calendar`
  lists all 51 flags.

## Handoff
- **Current state:** PR open, held for the batch (stacked on #575).
