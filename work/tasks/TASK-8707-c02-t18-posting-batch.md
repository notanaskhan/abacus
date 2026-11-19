---
id: TASK-8707
title: "C-02-T18: PostingBatchWorkflow and POST posting-batches over the W1 gate"
spec: SPEC-700
acceptance_criteria: [AC-3, AC-15, AC-17]
risk_zone: red
status: in-review
branch: c02-t18-posting-batch
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-02-T18
---

## Objective
adjustments/posting.py (the only W1 caller, POST-001): dry run (writer preflight, no write), POST posting-batches (fresh MFA via the matrix, Idempotency-Key, attest refused, entries stamped, single-use approval grant over the payload hash with not_before +10 s), Undo inside the hold (grant voided), and PostingBatchWorkflow (posting:<tenant>:<batch>, time sensitive) whose activity consumes the grant, re-reads ADR-344's switches through execute_write and posts each entry once ({batch}:{entry} key; already posted entries skipped), records results, sets the closing date once and emits posting_batch.posted.

## Plan (red)
1. integrations/writes.py: W1Scope, w1_refusal (attest, registry enabled, firm switch, engagement posting_enabled, client write grant, kill switch reader registered by C-02-T19), W1Refused (audited by refusal index), w1_ledger (client, QBO connection, entity name through connections/organisations), execute_write W1 path; integrations/api.py exports them and the writer types.
2. adjustments/posting.py, posting_types.py, posting_workflow.py; adjustments api registers the workflow (time_sensitive) and its activity.
3. posting_contract: dry-run, post and undo routes call the service (shapes unchanged).
4. error-codes.yaml: W1Refused under write_capability_refused.
5. Tests: tests/unit/adjustments/test_c02t18_posting.py (codes, digest, six entries 48213-48218 once under retries, closing date once, writer runs only with every switch on, W1 dark while the registry is disabled, attest refused).
6. Rollback: revert the routes to 501; W1 stays enabled: false in the registry (ADR-344 §10) so nothing reaches a client meanwhile.

## Progress log
- `2026-11-19` — Built; unit tests pass (6). W1 stays dark: write-capabilities.yaml keeps enabled: false until C-02-T50, so on any firm the batch fails closed `write_capability_not_released`; only a synthetic firm reaches the fake transport and only when the registry is enabled in tests. Kill switch reader: C-02-T19. DB-backed workflow test, replay history and the inline security review at the S51 end pass. Gates and tests run once at the S51 end pass (build first, test last).
