---
id: TASK-3200
title: T-03-T01 the T-03 protected bundle (matrix, flags, glossary, status rows, C16 kinds)
spec: SPEC-643
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: T-03
plan_key: T-03-T01
branch: s26-t03-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Generated tests deny the agent and portal principals every T-03 write and deny payment approval
to a user without the reviewer function."

## Plan (red)
- Matrix: `requests.yaml` gains `questionnaire.edit`, `questionnaire_template.draft` and
  `questionnaire_template.assign_owner`; `tax.yaml` gains `filing_extension.read/prepare/
  approve_payment/mark_filed/flag_likely/confirmation_send`, `estimate_schedule.read/update/
  confirmation_send` and `tax_schedule.export`. Every write: agent, system, client and
  third-party deny; `not_offshore: required` (fail closed, as DEC-2050). Approval:
  `function_in: detail_reviewer,manager_reviewer,signer`, never client service.
- Flags: `questionnaires.editor` (requests), `tax.extensions_estimates` (tax), default off.
- Glossary rows (organizer template/version, questionnaire section, answer effect, extension of
  time to file, extension payment, estimate schedule/installment, safe-harbor target); status
  objects `filing_extension`, `estimate_installment`, `questionnaire_template_version`,
  `answer_effect`; C16 kinds `extension_ack_rejected`, `extension_payment_approval_requested`,
  `estimate_due_soon`.
- Regenerated: `_matrix.py`, `_flags.py`, `_statuses.py`, `status.gen.ts`, `actions.gen.ts`, the
  generated security suites.
- Not here: `TABLE_OWNERS`/`IMMUTABLE_TABLES` ride with migration T-03-T03 (the schema check
  refuses rows for tables that do not exist; DEC-1550, DEC-2050). The publish row keeps T-02's
  roles until T-03-T05 adds template owners: `owner_of_target` now would fail closed for the
  seed's publish.
- Tests: `tests/unit/tax/test_t03t01_bundle.py` pins the rows.
- Rollback: revert the commit and regenerate.

## Progress log
- 2026-11-03: built. Kickoff (SPEC-643, TASK-3200..3034) rides here. Tests at the S26 end review.

## Decisions made during this task
DEC-2200.
