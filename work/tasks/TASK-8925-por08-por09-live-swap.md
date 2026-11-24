---
id: TASK-8925
title: "C-02-T41: POR-08 and POR-09 Copperleaf live swap"
spec: SPEC-701
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-c02t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T41
---

## Objective
Row acceptance: "Tess approves the August package on Sep 15 at 8:42 AM in POR-08 and CLS-08 shows Approved by client, while Ben Ashby sees only Copperleaf's entries." C18 close_package approval kind with the posted-entries card from C8 v2, approve and decline wiring to the C-02 applier, POR-09e package row.

## Done
- fs_package lists by engagement scope as well as close (entity-wide grants find it)
- decline: migration 1018 (declined_by_client, who/when/reason, sealed note), close back to review, audit close_package.client_declined, C16 package_client_declined
- CLS-08 package read carries the decline; status word Declined by client
- posted entries for non-attest clients as C18 state posted (read-only) for POR-08 Card B; portal posted bucket; status vocabulary posted
- POR-09: governed versions read Waiting for approval / Approved by you; Approve in Approvals → to POR-08; e live (DV-08 closed)
- gate catalogues brought current for earlier S53 rows (activity reviewed, audit owners, C16 kinds, C11 kinds, close agent modes, run-step test stubs)
- tests: unit test_c02t41_package_decision (5), test_c02t37 people (+decline); vitest POR-09 (+1), POR-08 green

## Progress log
- `2026-11-23` — Built and unit-tested; integration on the migrated DB (approve/decline round trip, Ben's scope) runs in the end pass with C-02-T36/T57.
