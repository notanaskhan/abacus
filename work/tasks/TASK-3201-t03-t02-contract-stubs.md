---
id: TASK-3201
title: T-03-T02 C5 additive questionnaires and answer effects, and the tax schedules API stubs
spec: SPEC-643
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T02
branch: s26-t03-t02 (stacked on s26-t03-t01)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Stubs freeze and the FE builds both screens in fixture mode against them while T-02's POR-05
contract tests stay green."

## Plan (amber)
- `requests/questionnaire_editor_contract.py`: nine routes behind `questionnaires.editor` (binder
  questionnaire, editor read, atomic PUT with dry run, client preview, template detail, owner,
  draft, discard, diff); T-02's publish route stays and gains its body in T-03-T05.
- `requests/answer_effect_slots.py`: `register_answer_effect` / `answer_effect_handler`, fail
  closed; `questionnaire_from_template` stub in `requests.api`.
- `tax/schedules_contract.py`: fifteen routes behind `tax.extensions_estimates` (extensions,
  prepare, submit, approve-and-request, patch, confirmation requests, estimates, installments,
  follow-ups, payments union, two exports).
- `make generate`; the schema set gained only new names (four clashes renamed: `TaxConfirmationOut`,
  `EstimateInstallmentOut`, `OrganizerTemplateRefOut`, `OrganizerTemplateVersionOut`).
- Docs: `questionnaires.md` §T-03 additive, `tax-extensions-estimates.md`, the contracts index,
  `docs/screens/BND-03.md` and `TAX-13.md` with deviations; the pen test #2 scope note (deferred,
  DEC-1389).
- Tests: `tests/contracts/t03/test_t03t02_stub.py`.
- Rollback: revert; regenerate the client.

## Progress log
- 2026-11-03: built. Tests at the S26 end review.

## Decisions made during this task
DEC-2201.
