---
id: TASK-6827
title: "Main CI after S36: event sets, generated client, S3 gateway, A-07 gallery artboards, WB-09 motion"
spec: SPEC-647
acceptance_criteria: [AC-P1]
risk_zone: amber
status: in-progress
branch: s36f-ci-reds
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-12
updated: 2026-11-12
plan_key: S36-CI
---

## Objective
Main `ci` on c9ebfb0eb (run 43080980016) goes green for the reds S36 caused or exposed.

## Plan and fixes
- `tests/unit/worker/test_worker_screening.py`: the publisher's exact event set gains S36's three
  subscriptions (`agent_run.completed` P-10-T42, `proposal.decided` and `proposal.undone`
  P-10-T38 and T-04-T31).
- `packages/api-client`: regenerated (`make generate`); the committed `openapi.json` lacked
  P-10-T42's `runs`, `starts_on` and `ends_on` and P-10-T39's 409 note. Fixes
  `test_openapi.py::test_ac20` and the schema and api-client job.
- `tests/integration/test_schema_check_db.py`: the immutable-table map gains 0812's
  `issue_runs`, `issue_fix_proposals` and `issue_explanations`.
- `tests/integration/test_p10t38_approved_writes.py`: `team` takes `object_store`, the session's
  S3 gateway, so `files.build_workbook` stores its workbook on CI (EndpointConnectionError: the
  local default names the dev gateway on 7070, present on a laptop, absent on CI; TASK-2927's
  lesson, made a second time).
- Gallery: AUD-18, AUD-19 and AUD-21 register on `/components/screens/<ID>` with their
  scenarios, as AUD-22 to AUD-25 do, so j03 15–16, j04 12 and j18 5 open them.
- `e2e/journeys/J03-ebp-audit.spec.ts` j03 19 (AUD-25 d): the artboard draws the logged addition;
  the empty-state sentence belongs to c. The step now asserts "Addition logged" and the approver.
- WB-09 c reduced motion: three colour transitions of the kit's `press` utility (180 ms, clamped
  to 0.01 ms) registered as running on a slow CI frame. `motion.css` now also sets
  `transition-property: none` under reduced motion, so no transition is created at all (nothing
  listens for transitionend).
- AUD-19 d/e: `aria-readonly` on the going-concern `<section>` is not an allowed attribute (axe
  aria-allowed-attr, critical, j04 12). It is `data-readonly` now; the unit test asserts it and
  that the card holds no control.
- j03 15 (AUD-18 c): the concurred card reads "Concurred · Oct 5, 2026 · …" and "G6 ✓" (handoff
  spec c); the step asserted the open card's title.
- AUD-22 c focus trap (gallery axe 2/3) failed once and passed on retry; it passes locally (flaky
  on a loaded runner, left as is).

## Progress log
- `2026-11-12` — Diagnosed from the run's logs. Built the fixes above.
- `2026-11-12` — Ran under the test lock: test_p10t38_approved_writes, schema_check ac20 and
  test_openapi (27 passed); J03, J04 and J18 fixture journeys (40 passed); agents-a11y and
  AUD-a07-a11y (54 passed); AUD-18/19/21 vitest (26 passed).
- Lesson made twice: an integration test that stores an object must take `object_store`
  (TASK-2927, then P-10-T38). Candidate lint: a test calling a storage-backed tool without the
  fixture.
