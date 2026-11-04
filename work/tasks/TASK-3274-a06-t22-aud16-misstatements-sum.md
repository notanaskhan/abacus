---
id: TASK-3274
title: A-06-T22 AUD-16 misstatements and SUM screen
spec: SPEC-000  # row (SPEC-642 F3, F4)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-06
plan_key: A-06-T22
branch: s27-a06-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Every AUD-16 artboard renders from its scenario with totals only from the server, '$' appears only
in the AJE list, and nothing reads Within threshold on an audit entry."

## Built
- Contract first (DEC-2254): `SumOut` gains the statement (rows by group with five signed
  columns, totals, footnote), the evaluation pane (thresholds with the materiality label, factors,
  booked entries, the `sum_conclusion` state, below-CT count and total, `aggregate_view`), the
  sign-off strip and the control bar's counts, all defaulted; `MisstatementOut` gains
  `description`; C8 gains `GET /v1/work-items/{wi}/proposed-entries:send-preview` (501 stub) for
  O3's recipient and template wording. Client regenerated; no schema clash. Contract test
  `tests/contracts/c08_adjustments/test_a06t22_aud16_contract.py`.
- `apps/web/src/screens/AUD-16/` (`Workbook.tsx`, `SendEntries.tsx`, `copy.ts`, `index.tsx`,
  `scenarios.ts`, test): control bar with counted views, tally strip, SUM statement table (no
  "$", parentheses, "—"), threshold bar (no donut; amber when approaching PM), qualitative factors,
  booked list, decision block with Request conclusion…, sign-off strip, AJE/RJE bento list with
  journal lines (the one place "$" appears), Below CT list, O3 send sheet with template wording
  and Undo (only the undo command).
- Evaluation page renders AUD-16 under Misstatements; `?ov=send-entries:<entryId>…` registered to
  the O3 sheet (convert and send-fs-draft stay planned). The Evaluation test's planned list drops
  misstatements, as A-06-T18 did for findings.
- Fixtures: `fixtures/seed/aud16.ts`, `fixtures/scenarios/AUD-16.ts` (a, b, b2, c, d, e, f, off,
  not_allowed).

## Progress log
- 2026-11-04: built; tsc and eslint clean on the new files. Tests written, run at the end pass.

## Decisions made during this task
DEC-2254.
