---
id: TASK-1856
title: Q-03-T061 contract-test upkeep, fixture-versus-live drift
spec: SPEC-045
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
epic: Q-03
branch: s12r-q03-t061
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Every consumer suite is green in provider CI and the drift count is zero at the quarter's end.

## Built
- `apps/web/src/fixtures/route-drift.test.ts`: every route fixture mode answers exists in the
  OpenAPI document (stubs included); a route ahead of its contract is listed by name with its
  defect, and the list must shrink.
- `abacus_tools.quality.report`: the "Fixture-versus-live drift" row now counts those routes
  (was "no data").
- ED-270: `PUT /v1/engagements/{engagement_id}/auto-mode` is answered by fixtures before
  P-10-T39 serves it (owner P-10-T39).

## Measured 2026-10-28
280 fixture routes; 1 not in OpenAPI (ED-270).

## Open
- Consumer suites in provider CI: `tests/contracts` at the end review.
- Unverified fakes: not measured yet.

## Progress log
- 2026-10-28: built; the drift test and report change not run yet (end review).
