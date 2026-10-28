---
id: TASK-1717
title: Q-04-T004 Flip guard in abacus_tools/flags.py and the entitlement CLI
spec: SPEC-403
acceptance_criteria: [AC-8, AC-9]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T004
branch: s14-q04-t004
created: 2026-10-28
updated: 2026-10-28
---

## Objective
P-29 rule 3 at flip time: for a pilot firm inside its window only the Tuesday 19:00–21:00 CT slot
unless `--hotfix`; `--approved-by` must be the other founder; `--rollback` required; `--all-off`
for one firm in one audited transaction; flip references in `feature_flag.set`. Acceptance
(backlog row): "An in-window flip outside the slot or approved by its own operator is refused with
nothing written, and an allowed flip records operator, approver and rollback ref."

## Plan (amber)
- `abacus_tools/flip_guard.py` (pure): `check(calendar, Flip) -> Verdict(why, window, pilot, refs)`,
  `next_slot`.
- `abacus_tools/flags.py`: `set_flag(..., refs)`, `all_off(...)`, `guard(...)`, CLI fields;
  `abacus_tools/tenants.py` entitlement takes the same guard and records the refs.
- `Makefile` `flag` and `entitlement`: `APPROVED_BY`, `ROLLBACK`, `REQUEST`, `HOTFIX`,
  `EVAL_REPORT`, `SHADOW_RUN`, `ALL_OFF`.
- DEC-807. Rollback: revert; unlisted firms keep SPEC-011's behaviour throughout.

## Acceptance
| Check | Test |
|---|---|
| In-window: slot edges, deadline week, mini-freeze, hotfix, approver, rollback, request, prompt variants; outside: approval and rollback only; unlisted firm: unchanged | `backend/tests/unit/tools/test_q04t004_flip_guard.py` (18) |
| Refused flip writes nothing (flag and entitlement CLIs); allowed flip records approver, rollback, request, slot; `--all-off` one event, no other firm; broken calendar fails closed | `backend/tests/integration/backfill/test_q04t004_flip_guard_writes.py` (5) |

## Progress log
- `2026-10-28` — Built. 18 + 5 passed; SPEC-011's `test_q03t050_feature_flags.py` still passes
  (25); ruff, pyright, lint-imports, banned patterns (CLOCK-001: time through
  `kernel.clock.system_now`, fixed here and on #574).

## Handoff
- **Current state:** PR open, held for the batch (stacked on #574).
- **Next:** Q-04-T005 (flag calendar), T010 (the ops-request file the flip names).
