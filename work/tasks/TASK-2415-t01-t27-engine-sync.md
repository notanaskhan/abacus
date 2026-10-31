---
id: TASK-2415
title: T-01-T27 Engine-sync read model, chip state function, gates and notification kinds
spec: SPEC-000  # the backlog row; T-01 §3.9 and the tax-engine-bridge contract
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T27
branch: s19-t01-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
GET engine-sync composing chip state, history, diagnostics and connection facts; the chip state
machine as a pure function with an exhaustive test over the seven states; C13 gate kinds
import_pending_approval and ready_to_transmit; notification kinds export_failed,
ready_to_transmit, efile_relocked and ack_rejected through C16.

Acceptance: "Every artboard state of TAX-09 is reproduced from seed events by the state
function, and HOME-02 shows the pending import to Samuel Ito."

## Progress log
- `2026-10-30` — Built on `s19-t01-t27` (stacked on `s19-t01-t25`, #892). The unit test passes
  (9/9); integration checks at the end review. DEC-1463.
