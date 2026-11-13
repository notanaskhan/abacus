---
id: TASK-7903
title: T-05-T52 Decision and gate kinds for the entity return
plan_key: T-05-T52
spec: SPEC-651
acceptance_criteria: [AC-F10]  # HOME-02 shows the §754 card with code facts; only the partner decides it
risk_zone: amber
status: in-review
branch: t05-t52-decision-gate-kinds
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
The §754 decision kind with code facts, five entity-return gate kinds, C16 kinds and realtime
topics for TXP-00's badges and TXP-01's stale banner.

## Plan (amber)
- Files: `tax/entity_decisions.py` (new: kind, provider, card raise, events, topics),
  `tax/entity_gates.py` (new: gate kinds and facts reused by T-05-T53), `agents/owner_reads.py`
  (new) + `agents/api.py`, `tax/run_steps.py` (raise after 706(d)), `tax/workbook_fix.py` (emit
  `workbook.fix_applied`), `notifications/catalogue.py` (two kinds), `tax/api.py`.
- No migration. Tests: `backend/tests/unit/tax/test_t05t52_decision_gate_kinds.py`.
- Rollback: revert the PR (raised cards stay as P-04 rows; the kind must stay registered while
  any exists).

## Partial
- The §743(b) figure (28,595 on the seed) needs T-06's basis owner; the card names the transfer
  and "Computed with partner basis" until then.
- The convention_706d options provider is T-05-T40's (no change).
- `tax_memo.went_stale` is emitted by T-05-T54.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4905 | gate kinds and owner reads | no |
| DEC-4906 | §754 kind, the run's raise, C16 kinds and topics | no |
