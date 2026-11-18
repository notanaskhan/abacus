---
id: TASK-8631
title: "T-06-T20: TB hand-off service in ledger (C12)"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: t06-t20-tb-handoff-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T20
---

## Objective
Spec section: docs/plan/epics/T-06.md §3 F6, §4.3. Code preview (prior-year tax-line mapping, suggested, blank; schedules carried; book income from the Final layer; tax items from C8 passed entries), create in one UoW behind a per-source-kind gate provider slot, supersede on a new Final snapshot after release, outbox tb_handoff.created/superseded.

## Plan (red)
1. ledger/tb_handoff.py: register_handoff_gate / source_released (fail closed), preview (pure; counts foot; preview_hash pins what was seen), create (409 handoff_not_available before release, 409 preview_changed on a moved preview; one version with account choices, schedules and tax items; a prior version gains a rehandoff supersession), supersede_for_snapshot (idempotent tb_changed_after_release rows).
2. Exported through ledger.api; HANDOFF-001 keeps it the only writer.
3. tests/unit/ledger/test_t06t20_tb_handoff_preview.py: Granite Peak 121 + 5 + 2 = 128 and book income 2,350,000; hash stability; an unregistered source kind is not released.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5631). Partial: the gate providers (assurance G8 for audit and review, closes for a locked close) and the C12 routes wiring in tax/tb_handoff_contract.py land with T-06-T25 (live swap); the DB acceptance (409 before release, one version after, one supersession) runs at the end pass. Gates and tests run once at the S50 end pass (build first, test last).
- `2026-11-18` — Gate providers built (S50 completion round): `assurance/handoff_gate.py` registers `audit_release` and `review_release` (released only once G8 `released()` returns a release); `closes/handoff_gate.py` registers `close_lock` (a Locked close only); each registers at its api import, ledger imports neither. Unit test pins the three registrations. Still with T-06-T25 (live swap): the C12 routes in tax/tb_handoff_contract.py.
