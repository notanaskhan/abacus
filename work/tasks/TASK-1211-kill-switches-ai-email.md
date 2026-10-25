---
id: TASK-1211
title: Kill switches part 1 — AI pause, model route block, email pause, operator command (Q-01-T36; P-66)
spec: SPEC-050
acceptance_criteria: [AC-21, AC-27]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T36
branch: s8b-core
created: 2026-10-25
updated: 2026-10-25
---

## Objective
Q-01 F8: stop AI or email for one firm or for everyone within seconds, without a deploy. The `platform_controls` table, its definers and the cached reader `kernel.controls.control_active` were on main (0086, 0156, P-08-T21); the enforcement points and the operator command were not.

## Plan
- `ai_gateway/boundary.py`: `ai_pause` (platform or firm) is the first check in `enforce_boundary`, which every completion and embedding passes just before its provider call; reason `ai_paused` appended to `REASONS`.
- `ai_gateway/__init__.py`: `model_route_block` skips a route in `_admitted`; `embed` answers `NotAdmitted` when its route is blocked.
- `communications/deliveries.py`: `deliver()` returns the violation (`platform_paused` checked first, then `suppressed`); `send_email` wraps it; contact invitations and follow-ups record the violation.
- `abacus_tools/platform_control.py`: `set` through `set_platform_control` as `abacus_ops` (argument checks first), `list` through `platform_control_state()`.
- Docs: platform-ops contract §3.7 "As built", `kernel/controls.py` readers, DEC-338.
- Tests: `tests/unit/ai_gateway/test_kill_switches.py`; `tests/integration/backfill/test_q01t36_t37_kill_switches.py` (email pause, operator command and audit).
- Rollback: revert; the controls stay readable and unenforced, as before.

## Progress log
- 2026-10-25: built with T37 (TASK-1212). Unit 14 passed; integration 4 passed. Within 10 seconds holds through the controls cache (`CACHE_SECONDS`); `ai_pause` and `read_only` fail closed when the state can't be read.
- 2026-10-25: security review fix round. `kernel.controls.control_state` tells an unreadable state from a pause; the boundary answers `NotAdmitted("controls_unavailable")` for it, so an outage never ends runs as `ai_paused`. Knowledge search maps a refused or deferred embedding to 503. Unit: 45 passed with the controls and boundary files.
