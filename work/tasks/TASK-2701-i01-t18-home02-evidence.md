---
id: TASK-2701
title: I-01-T18 HOME-02 evidence pane
spec: SPEC-000  # I-01-T18 row and docs/screens/HOME-02.md
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: I-01
plan_key: I-01-T18
branch: s22-i01-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "Evidence rows open SHL-08 on the cited region and the a and c evidence fixtures foot
  to the figures in the screen contract."

## Scope
**In**: `screens/HOME-02/{Evidence.tsx,sources.ts}` (the 576 pane: owner's summary, cited sources
in the E5 viewer, small segmented), detail source rows opening the SHL-08 drawer on the match, the
summary shape (`app-core/evidence-summary.ts`), HOME-02 a/c/d/g summaries and the transfer
agreement's page in fixtures, footing test, pane tests, gallery `summaryOf`.
**Out**: an owner read for summaries (T-05 / additive C3 field later; DV-4), TXP-08/TXP-01 links
(planned), NOT-02 analysis for the CP2000 item (N-04).

## Plan
1. Tests first: `fixtures/approvals-evidence.foot.test.ts` (basis columns, differences, calc
   card, capital rollforward) and `HOME-02.evidence.test.tsx` (a, c, d, g, the source row → SHL-08
   `?ov=viewer:`, the segmented → dock viewer, no summary → sources only).
2. Build the pane over the shared sources hook; the summary is a prop. Rollback: revert.

## Progress log
- `2026-10-31` — built; tsc, eslint, prettier clean on the touched files. Tests run at the S22 end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1751 (sources list, summary prop, fixture-only tax summaries) | no owner serves a summary yet (DV-4) | No |
