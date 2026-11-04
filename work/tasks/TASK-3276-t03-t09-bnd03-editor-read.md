---
id: TASK-3276
title: T-03-T09 BND-03 questionnaire editor read states and client preview dock
spec: SPEC-000  # row (docs/screens/BND-03.md BND-03)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-03
plan_key: T-03-T09
branch: s27-t03-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"BND-03a and BND-03e render in fixture mode with counts footing to 9, 4 and 8 of 9, and the dock
shows no tag, banner, helper or toggle."

## Built
- `packages/ui/src/questionnaire/client-question.tsx`: `ClientQuestionPreview`, the portal's
  question grammar (wording, Yes / No pills, amount rows, choices, upload link and Ignore, a
  "Required" marker) with no firm internals.
- `apps/web/src/screens/BND-03/` (`Editor.tsx`, `copy.ts`, `index.tsx`, `scenarios.ts`, test): the
  T2 frame: rail (template and answered KVs, sections with counts, Logic band with the amber review
  count), canvas (QuestionCards; the selected section's expanded with the Required toggle read-only,
  client wording, answer, follow-ups, "Not triggered", the review-point banner, the make-required
  and internal helpers; the empty-section state), dock (`…/client-preview` through the shared
  renderer, Desktop · Phone).
- Route `/binders/questionnaires/$questionnaireId?section=`; Requests and Activity return to BND-02.
  Manifest BND-03 is `fixture` with its path.
- Fixtures: `fixtures/seed/bnd03.ts`, `fixtures/scenarios/BND-03.ts` (a, e, off).

## Progress log
- 2026-11-04: built; tsc and eslint clean. Tests written, run at the end pass.

## Decisions made during this task
DEC-2256.
