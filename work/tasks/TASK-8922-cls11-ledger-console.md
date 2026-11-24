---
id: TASK-8922
title: "C-02-T35: CLS-11 ledger sync console, states a, a2, c, d, d2"
spec: SPEC-700
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-c02t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T35
---

## Objective
Row acceptance: "CLS-11a, a2, c, d and d2 render live on staging at Tier C and Request reconnect shows the POR-20 preview before sending." Build CLS-11 on the T1 variant (subbar with back chip, filter chips, status tiles that filter, connection pane KV with the olive tile, log pane Batches/Sync events, failures band) on the C20 W1 reads, with the reconnect confirm previewing the POR-20 email.

## Done
- screens/CLS-11 (copy, index, tests): a, a2, c, d, d2 from the exported Python scenario; tiles filter the log; Sync now/Retry now on ledger-pull; Export CSV
- route /clients/$clientId/entities/$entityId/ledger behind closes.gl_console; manifest live; CLS-07d opens it; back chip to.CLS02, Integration details ov.WB11
- additive W1 fields (amount, posted_at/by, authorized_at, status_reason, last_failed_at, reconnect_requested_at, company_name, failures, entry_ref) and the reconnect email preview route (filled_preview)
- sync events from finished runs on readable engagements; failed posts from failed attempts; tiles count batches (C-02-T20 tile test keeps its numbers over seven batches)
- cas_delivery_slice.cls11_console + scenario.cls11-console.json (Jan-Apr batches added from the canvas)
- tests: unit test_c02t35_console_reads (5), vitest CLS-11 (16), e2e/screens/CLS-11.spec.ts; screen contract, DEC-5924, c20 contract note

## Progress log
- `2026-11-23` — Built a, a2, c, d, d2 with backend additions; unit and vitest green; e2e walk and parity in the end pass. Also added KNW-04's deadline_overrides case (T-08-T44's kind surfaced by make generate).
