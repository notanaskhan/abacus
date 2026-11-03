---
id: TASK-3221
title: A-04-T26 AUD-08 c, e, f and g (linkage, revising, drafted values, identify risks)
spec: SPEC-620
acceptance_criteria: [AC-21]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T26
branch: s26-a04-t26 (stacked on s26-a04-t29)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"AUD-08 c, e, f and g render at Tier C, nothing auto-adopts, and with workpapers.drafting off every
agent control is absent and Check coverage shows the code result."

## Built
- `screens/AUD-08/AgentStates.tsx`:
  - `LinkageMatrix` (c: 13 px dots, R8 Suggested, "Link EBP-03…");
  - `RevisingHeader` (e: spinner and skeleton rows);
  - `DraftedMarker` and `DraftedFooter` (f: C-31; Adopt, Edit and Discard through C3's suggestion
    routes);
  - `IdentifyRisks` (g: code's coverage in an O1 with "Open R8 →"; "Check coverage" with
    drafting off).
- Register: tabs switch to Linkage; the control row's identify or check button; the `revising`
  prop. Drawer: drafted rationale is ink-2 with its marker and footer.
- Fixtures: c, e, f, g and drafting_off; R8's drafted drawer seed.
- Tests: `screens/AUD-08/AUD-08.test.tsx` (four new cases).

## Progress log
- 2026-11-03: built. Partial: e's `revising` comes from the host (`RiskRegisterPage revising`)
  until the re-draft consumer's run status exists (A-04-T29 deferral). The "Link EBP-03…"
  picker opens with A-04-T38's link picker. Tests and parity at the S26 end review.
