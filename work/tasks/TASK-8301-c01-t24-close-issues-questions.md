---
id: TASK-8301
title: "C-01-T24: Close issues and transaction questions"
spec: SPEC-655
acceptance_criteria: [AC-44, AC-45, AC-46, AC-47]
risk_zone: amber
status: in-review
branch: c01-t24-close-issues
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T24
---

## Objective
Spec section: docs/plan/epics/C-01.md §3 F8.
Close issues and transaction questions.

## Plan (amber)
1. `closes/issues.py`: the `close` reviewable (facts from the close row), `raise_exception` (P-04 kind `exception`, priority = severity band, path `close/<class>`, engine exceptions deduplicated on `close:<class>:<account>:<line>`), `add_note` (`close_note/<class>`, never counted), `close_issues` (CLS-06 queue, facets, badge), `ask_question` (authorise `transaction_question.send`, outbound scope check, write on the close's intake binder).
2. `requests/transaction_questions.py` (shared API, exported from `requests.api`): `ask`, `questions_for`, `answer` (addressed contact only, sealed, fulfils the linked request item; with an evidence version, `fulfil_by_upload` in the same unit of work).
3. `review/issues.py`: `IssueRow.source_ref` (additive) so a close issue names its account and register line.
4. `closes/contract_work.py`: the issues and ask routes call the service; `TransactionQuestionIn.template_id` is the template key (text), as the table holds it.
5. Audit: `transaction_question.sent/answered` reviewed; `transaction_question` audit owner in `requests/audit_targets.py`.
6. Tests: `tests/integration/test_c01t24_close_issues.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5301). Lint and pyright clean on the touched files; the app imports. Gates and
  tests run once at the S47 end pass (build first, test last).
