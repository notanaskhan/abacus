---
id: TASK-7902
title: T-05-T51 TXP-10 read model and actions over C3 issues
plan_key: T-05-T51
spec: SPEC-651
acceptance_criteria: [AC-F8]  # 5 + 6 = 11 equals the badge and TXP-00; client wording never shows the internal note
risk_zone: amber
status: in-review
branch: t05-t51-entity-issues
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
TXP-10's queue (Waiting on the client, Review points, counts per step, filters, search) and its
actions (assignee picker, send to the client with template wording, reminder, resolve with note).

## Plan (amber)
- Migration 0870 (on 0860): `tax_issue_resolution_notes` (insert-only, forced RLS, sealed note).
- Files: `tax/entity_issues.py` (new), `tax/workbook_contract.py` (the 501 issues route
  implemented, assignees, send-to-client, reminders, resolve), `tax/registry.py`,
  `review/issues.py` + `review/api.py` (`issue_links`, `send_issue_to_client`,
  `issue_run_facts` exports), `engagements/api.py` (`engagement_roster`),
  `audit_trail/activity_reviewed.py`, contract note.
- Tests: `backend/tests/unit/tax/test_t05t51_entity_issues.py`.
- Rollback: revert the PR, downgrade 0870 (notes are sealed copies; issues are P-04's).

## Partial
- A client contact is reached by sending to the client; P-04's issue row has no client-contact
  assignee field, so the queue never shows one as the assignee.
- Agent-off and consent-blocked states (T-05-T66) read P-04's own `allowed_actions`.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4903 | queue composed from P-04 readers; sections, counts, step by sheet | no |
| DEC-4904 | client wording only, template reminders, sealed resolution note (0870) | no |
