---
id: TASK-2128
title: N-01-T21 Matcher v3 intake eval cases
spec: SPEC-033
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T21
branch: s16-n01-t21
created: 2026-10-29
updated: 2026-10-29
---

## Objective
An intake section in the protected matcher suite (`evals/matching/suite.yaml`): right-year vs
prior-year 1095-C, W-2c, corrected 1099-DIV, a census xlsx to an audit request, a card receipt, an
unrelated vendor invoice, a cross-client lookalike, an instruction-in-file PDF and a unicode
deception; intake thresholds of its own; a fake-model fast run in `make check`.

Acceptance (backlog row): "Existing thresholds are unchanged and the intake section runs in make
check with the fake model."

## Plan (red)
- Suite: `intake:` block (covers, thresholds, cases); the audit thresholds and 30 cases untouched.
- Harness (`abacus_tools/evals/matching.py`): `IntakeSection`, `INTAKE_REQUESTS`,
  `_intake_documents`, validation, `--section intake`; on `--route fake` the recorded matcher
  answers (`fake_answers/matching_intake.yaml`) stand in for the model after the real extraction,
  content rules and file-name baseline. Synthetic generators: `w2c_pdf`, `form_1099_div_pdf`,
  `census_xlsx`.
- `make evals-match-fast` added to `make check`.
- Tests: `tests/unit/tools/evals/test_n01t21_matcher_intake.py` (audit thresholds pinned, intake
  validates, recorded answers clear the intake thresholds, documents, the make target).
- Rollback: revert; the suite's audit section and its thresholds are unchanged.
- Review: protected suite; N approves the cases and thresholds at the batch merge.

## Progress log
- 2026-10-29: built. DEC-1175.
