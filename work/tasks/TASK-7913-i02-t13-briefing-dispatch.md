---
id: TASK-7913
title: I-02-T13 Briefing dispatch and freshness
plan_key: I-02-T13
spec: SPEC-654
acceptance_criteria: [AC-F3]  # one run per engagement on concurrent opens; unavailable with zero model calls; signed gate drops its why
risk_zone: red
status: in-review
branch: i02-t13-briefing-dispatch
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
`ensure_briefings`: idempotent claimed dispatch per viewer, engagement and day, three at once,
pre-checks without a model call, modes and debounce, the day snapshot, why-line freshness,
`daily_briefing.built` on the user topic, and the builds route.

## Plan (red)
- Migration 0871 (on 0870): `facts_hash` updatable on `daily_briefings`.
- Files: `agents/briefing/dispatch.py` (new), `agents/briefing/today.py` (complete the claimed
  row; newest finished row for the hash check; emit the event), `agents/api.py`,
  `agents/registry.py`, `practice/today/assembly.py` (why lines), `practice/today/routes.py`
  (builds), `audit_trail/activity_reviewed.py`.
- Tests: `backend/tests/unit/agents/test_i02t13_briefing_dispatch.py`.
- Rollback: revert, downgrade 0871 (claimed rows still complete by insert).
- Security review: at the S42 end pass (red).

## Partial
- Work class: dispatch rides P-10's engagement run (interactive and background share its class);
  the mode is audited.
- The staleness trigger (background mode) is called by the Today read when `needs_build` is set
  (I-02-T15's screen) and by the 15-minute poll; no scheduled job here.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4916 | claimed dispatch, limits, provider, 0871 | no |
| DEC-4917 | why-line freshness; snapshot without text | no |
