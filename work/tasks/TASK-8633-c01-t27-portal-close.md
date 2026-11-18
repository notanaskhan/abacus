---
id: TASK-8633
title: "C-01-T27: Portal close read model: POR-11 transaction questions and answers"
spec: SPEC-656
acceptance_criteria: [AC-47]
risk_zone: amber
status: in-review
branch: c01-t27-portal-close
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: C-01-T27
---

## Objective
Spec section: docs/plan/epics/C-01.md §3 (POR-11). The close_intake binder in the POR-03 read model, the transaction questions list and answer (shared POR-04 e), client words only; a Copperleaf grant cannot read any other client's close (INV-4).

## Plan (amber)
1. closes/portal_questions.py: mine (questions addressed to a contact the signed-in person holds; another client's close answers an empty list), context_line (code facts only), answer_text (POR-04 choice words + note), answer (requests.api answer_transaction_question; sealed).
2. closes/contract_work.py: the two POR-11 portal routes wired (questions list and answer).
3. tests/unit/closes/test_c01t27_portal_questions.py.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5633). Partial: the close_intake binder already reaches POR-03 through requests (C-01-T19); the period picker, connected-source suppression, payout summary lines and mark done/undo to CLS-03 extend the POR-03 read model with the POR-11 screen task (C-01-T41); the answer's attachment path rides the portal upload route then. The DB acceptance (Ben Ashby 9 requests, 7 received, 2 open, 3 questions) runs at the end pass with the seed. Gates and tests run once at the S50 end pass (build first, test last).
