---
id: TASK-8920
title: "C-02-T39: Close-to-tax hand-off (closes side) over C12"
spec: C-02
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-c02t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: C-02-T39
---

## Objective
Row: "Close-to-tax hand-off (closes side): availability (December close and Locked), preview from the locked snapshot with tie, schedules carried, tax-relevant resolved close issues; TaxHandoffWorkflow calling C12 to land the UTB with provenance on the 2026 Form 1120-S, tax issues on the TXP-10 route, notifications; supersede on reopen; TJEs never post." Acceptance: "Priya's hand-off on Jan 12, 2027 lands TB v1 with three tax issues for Olivia Brandt and Samuel Ito, and a hand-off after the Jan 20 reopen supersedes it."

## Done
- closes/tax_handoff.py: availability gate, preview (TB vN, tie, target, five schedules by code, tax-relevant notes), publish via ledger tb_handoff.create (close_lock) with close_issue items, closes tax_handoffs row, supersede on re-lock, tax_handoff.published/.superseded to preparer and reviewer
- tax.api.handoff_target (return, engine, preparer, reviewer); landing title for close_issue
- migration 1017: C12 schedule kinds and close_issue item kind; ledger/tb_handoff.py (red) Literals widened
- CLS-12 routes live; DeliveryHandoffOut.items and .balanced additive
- tests: unit 5 pass; integration test for the end pass; DEC-5922

## Progress log
- `2026-11-23` — Built in full. Red diff: ledger/tb_handoff.py Literal widening needs the end-pass security review. End pass: make generate, integration test.
