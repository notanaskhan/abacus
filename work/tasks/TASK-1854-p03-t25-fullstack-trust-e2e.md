---
id: TASK-1854
title: P-03-T25 full-stack E2E on staging, trace to source and PII reveal/unlock
spec: SPEC-020
acceptance_criteria: [P-03-T25]
risk_zone: green
status: in-review
epic: P-03
branch: s12r-p03-t25
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Both specs pass nightly against staging with INV-1 to INV-5 asserted in the browser and database.

## Built
- `e2e/journeys/J04-fs-audit.spec.ts` (the plan's "J04-pbc-slice"): the trace-to-source test.
- `e2e/trust/pii-reveal-unlock.fullstack.spec.ts`: masked W-2, logged reveal, offshore refusal,
  password PDF unlock. Hosted runs read the synthetic upload ids and the synthetic password from
  `ABACUS_E2E_W2_VERSION`, `ABACUS_E2E_LOCKED_VERSION`, `ABACUS_E2E_LOCKED_PASSWORD`.
- `playwright.config.ts`: `**/*.fullstack.spec.ts` joins the harness projects.

## Open
- The nightly staging job stays off until `STAGING_JOURNEYS` is on; three nights then count.
- The seed must write the synthetic W-2 and password PDF on staging and expose their ids.

## Progress log
- 2026-10-28: written; not run (needs the full stack or staging).
