---
id: TASK-8708
title: "C-02-T19: W1 write evidence under Object Lock and the ledger write kill switch"
spec: SPEC-700
acceptance_criteria: [AC-21, AC-23]
risk_zone: red
status: in-review
branch: c02-t19-write-evidence
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-02-T19
---

## Objective
Every W1 call leaves a ledger_write_operations row (sent → verified, failed or verify_mismatch; one per idempotency key, attempts counted) and three write-once bodies (request, response, read-back) stored with SHA-256 under Object Lock (COMPLIANCE, record class ledger_write_evidence). The per-firm kill switch ledger_write_pause (migration 0981) is read uncached, so a flip refuses the next write within one call (write_capability_disabled), failing closed when unreadable.

## Plan (red)
1. Migration 0981 (on 0980): platform_controls and platform_control_changes accept ledger_write_pause.
2. kernel/controls.py: ControlName ledger_write_pause; control_active_now (uncached, fail closed).
3. evidence/records.py: record class ledger_write_evidence.
4. integrations/writes.py: W1Operation, W1Evidence, _open_operation/_close_operation inside execute_write's W1 path; the kill switch reader registered.
5. adjustments/posting.py: each create_journal_entry and set_closing_date passes its operation and evidence mapping.
6. Tests: tests/unit/adjustments/test_c02t19_write_evidence.py.
7. Rollback: downgrade 0981 removes the control's rows; evidence rows are insert-only by design.

## Progress log
- `2026-11-19` — Built; unit tests pass (3) and C-02-T18's still pass. Partial: a verify_mismatch is recorded as its status and audited, but flipping the firm's kill switch and opening the SEV2 under RB-30 need the operator role (set_platform_control is abacus_ops only), so they stay with the runbook. DB-backed evidence test at the S51 end pass. Gates and tests run once at the S51 end pass (build first, test last).
