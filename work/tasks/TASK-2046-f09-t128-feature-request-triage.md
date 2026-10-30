---
id: TASK-2046
title: F-09-T128 Partner feature requests triaged against D1-D10 and X-01..X-08
spec: SPEC-049
acceptance_criteria: [AC-38]
risk_zone: green
status: blocked
epic: F-09
plan_key: F-09-T128
branch: s15c-f09-t128
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Partner feature requests triaged against D1-D10 and X-01..X-08, with written answers; every request
has a written answer naming the epic, the deferral or the exclusion.

## Built
- `docs/ops/pilot/feature-requests.md`: the rules, how to classify (epic, deferred, excluded) with
  the Scope Decision Record's D and X titles, and the log.
- `abacus_tools.quality.feature_requests` in check-fast: pilot codes only; each verdict names what
  it must (an existing epic, an epic's cut list or D10, an X-area or D4/D6/D7/D8); every row has its
  answered-on date and vault reference.
- SPEC-049 AC-38; tests `backend/tests/unit/quality/test_feature_requests.py` (end review).

## Blocked on
Requests themselves: Pilot 0 has not run.

## Progress log
- 2026-10-30: log, check and AC built.
