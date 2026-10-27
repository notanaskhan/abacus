---
id: TASK-1708
title: Q-03-T525 back-fill TASK-023 (engagement graph and methodology v1) and TASK-063 (comments web)
spec: SPEC-008
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T525
branch: s14-q03-t525
test_author: ayushkbhatia
test_session: 2026-10-28, s14 (from SPEC-008 and SPEC-032 only, black-box)
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 back-fill, headed `ac-test-author: ayushkbhatia`, a named `test_ac<N>` for every AC of
SPEC-008 (TASK-023, live until K-01 replaces it in S26) and SPEC-032 (TASK-063, comments web, live
until P-05 in 2028). With T524 this closes the 55 owed tasks' acceptance suites at M8.

## Plan and coverage
SPEC-008: `backend/tests/integration/backfill/test_q03t525_engagement_graph_methodology.py`
over HTTP (import, apply, graph), a ledger snapshot seeded by SQL.
| AC | Tests |
|---|---|
| AC-1 | stored version with its areas, items and rules; `methodology.imported` audited with the fingerprint |
| AC-2 | 5 bad workbooks (duplicate area, unknown area, bad tier, malformed rule, not xlsx): 422, nothing stored, no cell text echoed |
| AC-3 | same name gives version 2; the app role cannot update or delete a version |
| AC-4 | apply pins, one item per template item with area name and tier, audited; staff refused |
| AC-5 | a second apply is 409 `methodology_already_applied`, items unchanged |
| AC-6 | graph: engagement, team, methodology, every area with its items |
| AC-7 | accounts map by rule order; the rest unmapped |
| AC-8 | gaps: areas without requests, areas with accounts but no requests, non-zero unmapped (Q5), items without evidence |
| AC-9 | walled, outsider and another firm read the same 404 as a missing engagement |

SPEC-032 (TASK-063): `apps/web/src/legacy/q03t525comments.test.tsx`, 17 tests: AC-1 (version
thread), AC-2 (internal by default, share, client always shared), AC-3 (client sees only what is
returned, no internal affordance), AC-4 (no edit/delete; correction linked both ways), AC-5
(mentions from the server's candidates, sent once), AC-6 (redact only for admins, needs a reason,
stub for every reader), AC-7 (scope violation reasons and the internal-note path), AC-8 (read
marking; the Board count and filter are `board/filters.ts`'s), AC-10 (loading, error,
not-allowed, internal distinct). AC-9 (sealed at rest, never logged, audit with identifiers) and
AC-3's server filtering are TASK-062's: `test_q03t039_comments_and_drafter.py` (Q-03-T039).

## Progress log
- `2026-10-28` — Suites written. Web 17 passed (targeted). The SPEC-008 integration file (ruff and pyright clean) runs in the batch-end pass.

## Handoff
- **Current state:** PR open, held for the S14 batch.
- **Known gaps:** SPEC-008 integration file not yet run.
