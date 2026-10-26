---
id: TASK-1302
title: Screen contracts HOME-01 and HOME-02 (I-01-T01)
spec: SPEC-307
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
epic: I-01
plan_key: I-01-T01
branch: s10-i01-screen-contracts
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Both contracts list every artboard and spec-only state with data condition, persona, clock and tier", with the DF-25 band rule, the DF-39 five-option segmented control, the rationale-always deviation, planned targets, copy keys, figures and AVOID. I-01 has no SPEC; the frontmatter names SPEC-307 AC-6 (the seed's golden list), which the contracts' Figures sections feed.

## Plan (green, docs only)
- **Files:** `docs/screens/HOME-01.md` (a, a2, spec-only b–e per DF-06, f, g, h, i; interaction states office-denver, tile-popover, today-brief-off; walled and other non-artboard states) and `docs/screens/HOME-02.md` (a–g; catalogue states show-done, snoozed, reassigned, overdue), from `_TEMPLATE.md` and the handoff (README, spec, revision R2 for HOME-01; TPL-11 for b–e).
- **Decision:** DEC-403 records DF-25 (with OQ-2's `evidence_review`), DF-06, DF-39, OQ-1, OQ-3, OQ-4, OQ-7, OQ-8 and the HOME-02g count, under the solo amendment (N's Contract Monday sign-off is a formality).
- **Figures:** every footing figure checked against the handoff by hand (tiles, 11 = 3 + 6 + 2, PTET, Whitley, materiality, basis table, calc card, capital rollforward).
- **Tests:** none run here; `validate_docs` only. The footing tests are I-01-T05 and T15.
- **Rollback:** revert the commit (docs and one decision-log row).

## Progress log
- 2026-10-26: both contracts written from the handoff and screenshots; DEC-403 appended; `validate_docs` run. Gaps recorded in each contract's Open gaps (HOME-02g's "Approvals 2", h/i frames reusing Daniel's data, the "Ready" tile word, the C13 slot name).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-403 | DF-25, DF-06, DF-39 and the HOME deviations decided with the plan's options | No |
