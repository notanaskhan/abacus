---
id: TASK-3275
title: N-04-T14 NOT-02 notice workspace screen
spec: SPEC-000  # row (docs/screens/NOT-02.md NOT-02)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T14
branch: s27-n04-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Scenario tests for a, b, c, d and a2 pass, a lit payer lights in all three panes, and Kevin Osei
sees the decision radios disabled with the reason in text."

## Built
- `apps/web/src/screens/NOT-02/` (`Workspace.tsx`, `copy.ts`, `index.tsx`, `scenarios.ts`, test):
  subbar (title, status pill, respond-by), Analysis · Response · Activity tabs, three 452 panes:
  the viewer (SHL-08 ViewerPane; "1 / 2" when the source row is lit), the analysis pane
  (segments, statement rows from `AnalysisOut.rows`, information returns, Why This Was Surfaced
  through AgentText with off/shadow and refused states, running spinners and progress line), the
  action pane (Proposed action with the source row and jump, Draft response or Start, the inline
  `notice_position` card: radios and rationale only for the reserved signer, the reason in text
  otherwise, decided read-only; the authorization card with the 8821 note). Payer rows and the
  source row light the same payer across panes on hover and focus.
- Route `/notices/$noticeId` (`?tab=`, `?segment=`); Decide opens SHL-11 (`?ov=decision:<card>`).
  Manifest NOT-02 is `fixture` with its path.
- Fixtures: `fixtures/seed/not02.ts`, `fixtures/scenarios/NOT-02.ts` (a, b, c, d, a2, off).

## Progress log
- 2026-11-04: built; tsc and eslint clean on the new files. Tests written, run at the end pass.

## Decisions made during this task
DEC-2255.
