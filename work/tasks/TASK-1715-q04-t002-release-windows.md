---
id: TASK-1715
title: Q-04-T002 deploy/windows.yaml and abacus_tools/release_windows.py
spec: SPEC-403
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T002
branch: s14-q04-t002
created: 2026-10-28
updated: 2026-10-28
---

## Objective
The P-29 freeze contract as one file and one module: `deploy/windows.yaml` (windows 2027–2029, the
Tuesday slot, the 20:00 CT migrate time, firms by pilot code) and `abacus_tools/release_windows.py`
(validation, `in_window`, `platform_window`, `deadline_week`, `mini_freeze`, `flip_slot`,
`migrate_not_before`, the calendar CLI); `make windows`; validation in `make check-fast`.
Acceptance (backlog row): "make windows prints the 2027-2029 calendar of section 4.9 and check-fast
fails on an overlapping, undated or unknown-tenant entry."

## Plan (amber)
- `deploy/windows.yaml`: five windows from Q-04 §4.9; `firms: []` until PW1 (DEC-68).
- `release_windows.py`: parse and validate (every problem named); the IRC §7503 shift with DC legal
  holidays; each window's dates checked against the rule; guards in Central time.
- `Makefile`: `windows` target; `release_windows check` in `check-fast`.
- SPEC-403 (AC-1 to AC-13 for the whole Q-04 lane); DEC-806.
- Rollback: revert the branch.

## Acceptance
| Check | Test |
|---|---|
| AC-1 PF-A1 in autumn-2027 from Sep 1 00:00 CT; audit-only firm none until Jan 1, 2028 | `backend/tests/unit/tools/test_release_windows.py::test_ac1_*` |
| AC-2 no live firm: every guard inert | `…::test_ac2_with_no_live_firm_every_guard_is_inert` |
| AC-3 overlap, undated, rule drift, no code, non-pilot code fail naming the entry | `…::test_ac3_*` |
| AC-4 the §4.9 calendar for every window; YEAR=2027 mini-freezes | `…::test_ac4_*` |
| Slot edges, deadline shifts, migrate time, CLI | the rest of the file (50 tests) |

## Progress log
- `2026-10-28` — Built. 50 passed; ruff, pyright; `make windows` prints §4.9 exactly.

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** Q-04-T003 (release gate), T004 (flip guard), T005 (flag calendar) read this module.
