---
id: TASK-9001
title: "F-01-T05: CV-2 money-path coverage back-fill (S54)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s54-cv2-money-path-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: F-01-T05
---

## Objective
DEC-6003 CV-2: tests for the core money paths (adjustments posting, integrations W1 writes, closes reconciliation, firm setup tooling) that run them on the migrated database.

## Done
- tests/integration/backfill/test_cv2_w1_posting.py: 14 cases, the W1 path end to end through its routes and activity (switches, dry run, batch, hold, undo, run, replay, failure, retry, closing-date conflict, re-date, ask-client refusal, reversal, export, record externally, GL settings)
- tests/integration/backfill/test_cv2_eliminations.py: 4 cases (propose off balance, edit, approve, post, reject, locked, roles, DB refusal past draft)
- tests/integration/test_cv2_reconciliations.py: 3 cases (pending, statement version, carry, resolve once, AJE from item, L1 block, ledger snapshot recompute)
- tests/unit/integrations/test_cv2_qbo_http_transport.py: 18 cases (URLs, bodies, request ids, error mapping, read-back)
- tests/unit/tools/test_cv2_tenants_cli.py: 25 cases (every command's dispatch and refusals)
- Defects found and fixed: ED-340 to ED-347 (migrations 1030, 1031; DEC-6006, DEC-6007)
- Measured on the touched files: posting 37->86%, posting_recovery 30->77%, eliminations 30->82%, closes reconciliations 34->96%, QBO writer 68->97%, w1_switches 53->84%, w1_contract 81->94%, ledger_console 83->95%

## Progress log
- `2026-11-26` — Built; new suites green locally (14 + 4 + 3 integration, 43 unit). Not covered: ask-client's send (needs an approver of record and the firm's lift template imported), decisions.py and contract.py beyond what their suites run; tax back-fill is a later batch (DEC-6003).
