---
id: TASK-1716
title: Q-04-T003 Release gate in deploy-production.yml and make release-check
spec: SPEC-403
acceptance_criteria: [AC-5, AC-6, AC-7]
risk_zone: red
status: in-review
epic: Q-04
plan_key: Q-04-T003
branch: s14-q04-t003
created: 2026-10-28
updated: 2026-10-28
---

## Objective
P-29 at promotion time: while any live firm is in a window, a production release carries
`window_mode` and a rollback link, promotes only in the Tuesday slot, is refused in a deadline week
unless it is a named hotfix (counted), and its migrate step waits for 20:00 CT. Acceptance
(backlog row): "On a simulated in-window date a release PR without a rollback link fails, a
deadline-week release passes only with hotfix set and a reason, and once Q-03-T081 lands a drop …
fails" (the last clause is Q-03-T081's guard, called by the gate when it lands).

## Plan (red)
- `abacus_tools/release.py`: optional production keys `window_mode`, `rollback`, `hotfix` with
  their forms; `window_gate(release, calendar, at)` → refused reasons, window, deadline week,
  in-window hotfix, migrate-not-before; CLI `window-gate`.
- `deploy-production.yml`: the window gate in the Gates step (summary line: window, in-window
  hotfix); a "Hold the migrate step for the window" step before Migrate (at most 75 minutes; job
  timeout 180).
- `make release-check [AT=]`; `deploy/production/README.md` documents the fields.
- No migration guard here: Q-03-T081 owns contract-operation checks (Q-04 AC-2.4).
- Rollback: revert; outside every window (today: no live firm) the gate is inert anyway.

## Acceptance
| Check | Test |
|---|---|
| AC-5 in-window release without window_mode or rollback refused; outside a window or with no live firm, nothing required | `backend/tests/unit/tools/test_q04t003_release_window_gate.py::test_ac5_*` |
| AC-6 deadline week needs hotfix with reason and handle; counted | `…::test_ac6_*` |
| AC-7 migrate held to 20:00 CT; the workflow gates, then holds, then migrates | `…::test_ac7_*`, `…::test_the_workflow_gates_then_holds_the_migrate_step` |
| Slot-only promotion; field forms; CLI; placeholder | the rest (21 tests) |

## Progress log
- `2026-10-28` — Built. 21 passed; existing release, deploy-workflow and release-path suites
  (49) still pass; ruff, pyright, lint-imports.

## Handoff
- **Current state:** PR open, held for the batch (stacked on #573).
- **Next:** Q-03-T081 plugs its contract-operation guard into the gate in window mode.
