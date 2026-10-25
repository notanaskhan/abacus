---
id: TASK-1223
title: C-34 ScreeningCard kit, SHL-20 a–f, follow-up sheet, ReturnDialog, View → SHL-08, feedback picker; BND-02 g and R2 rows (P-06-T22)
spec: SPEC-319
acceptance_criteria: [AC-24, AC-26]
risk_zone: green
status: in-review
epic: P-06
plan_key: P-06-T22
branch: s8b-evidence-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Seven scenarios render, feedback cannot be sent without a reason, and no confidence percentage
appears anywhere." (SHL-20 a–f and BND-02 g.)

## Plan
- **Kit (L2):** `packages/ui/src/components/screening/ScreeningCard.tsx` (C-34: flagged, passed,
  not screened, running, loading; header, two checks, flagged band with View · Return…, footer,
  provenance), specimen `c-34-screening-card`, kit tests.
- **Domain:** `apps/web/src/domain/screening/` (`queries.ts` 2 s poll while running, `compose.ts`
  code-worded answers, `ScreeningCardHost.tsx`, `FeedbackMenu.tsx`, `copy.ts`);
  `domain/requests/ReturnDialog.tsx` (reason catalogue, "Wrong document" preselected) and
  `ScreeningReturnSheet.tsx` (O3, DV-1).
- **Screens:** `screens/SHL-20/` (frame, artboards a–f, tests); BND-02 g and the R2 rows (Linked
  (n), glyph, dock card, Accept / Return…, "Open in viewer" → SHL-08).
- **Contract (additive):** `ScreeningCardOut.request_title`, `period_start`, `period_end`
  (`agents/screening_card.py`, `screening_contract.py`), `make regenerate`, contract doc §12.
- **Fixtures:** `fixtures/seed/screening.ts`, `fixtures/scenarios/SHL-20.ts`, BND-02 g scenario and
  the R2 row fields in `seed/binder-detail.ts`.
- No migrations, flags or matrix rows. **Rollback:** revert the commit.

## Scope
**Out (deferred)**
- The server's screening-return draft and its send (`POST …/request-items/{id}/follow-ups` answers
  501; C5 §12 assigned it here): red backend work in agents/requests/communications (template
  composition from `notification.follow_up_sent.screening_return`, two `send_back` decisions, the
  request returned and the shared comment in one unit of work, Undo). Needs its own red task.
- "Add a to-do for me" (P-05), "Link to request…" (INB-02, N-01), SHL-21 behind Linked (n) (K-04).
- AUD-03 / CLS-03 hosting (A-01, C-01).

## Progress log
- 2026-10-25: built. Kit 4 tests; SHL-20 19 tests; BND-02 +6 tests (28 total); backend contract
  +1 and integration +1. Status `in-review` because the screening-return draft backend is deferred
  (DEC-351): the live "Draft follow-up" toasts an error until it lands.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-351 | The card carries no answer text; answers by code, reasons from verified citations, request facts added to the card; the draft endpoint is still a stub | No |
