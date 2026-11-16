---
id: TASK-8075
title: "C-01-T35: CLS-03 Intake states a, a2, a3, b, c, d, e, f, g and h on T9 close-review"
spec: SPEC-655
acceptance_criteria: [AC-2]
risk_zone: green
status: in-review
branch: c01-t35-cls03-intake
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T35
---

## Objective
CLS-03 Intake inside the close shell: the request tree, the detail cards with the summary's cited
totals, the viewer's zebra sheet, Incorporate and Return to client (a person's click only), the
re-run offer, requested rows, the questionnaire, upload on behalf, not yet published, and the R2
screening states.

## Built
- `screens/CLS-03/index.tsx`, `copy.ts`, `scenarios.ts`; the route renders it as the Intake body.
- `fixtures/seed/close-intake.ts` (tree, Square payout sheet, summary, questionnaire, verbatim
  from the handoff); `fixtures/handlers/closes.ts` serves the tree, questionnaire and summary;
  `fixtures/scenarios/CLS-03.ts` a–h.
- Backend: `RequestNodeOut` gains `evidence_version_id` and `due_on` (the viewer's file and the
  requested row's due date; additive), filled by `closes.intake.request_tree`.
- `screens/CLS-03/CLS-03.test.tsx` (9 pass locally); client regenerated.

## Progress log
- `2026-11-15` — Built; vitest and `tsc` clean. Tier C parity and axe at the end pass.
- **Deviations:** the tree's dated sub-lines ("Incorporated Sep 3", "Requested Sep 1") need the
  request's history dates on the node (C-01-T42 live swap); until then the status word and due date
  show. The viewer's header names the sheet; the file name rides on the evidence version (C-01-T42).
  The R2 ScreeningCard body is P-06's `ScreeningCard`, wired at the live swap with its verdicts.
