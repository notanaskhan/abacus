---
id: TASK-1338
title: AUD-06 remaining states in fixture mode, b, d, e, g and h (A-02-T14)
spec: SPEC-333
acceptance_criteria: [AC-14]
risk_zone: green
status: in-review
epic: A-02
plan_key: A-02-T14
branch: s10b-ledger-integrations
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Each state matches its scenario, the agent never shows initials, and Hand off to tax and the
entity strip are absent from production builds."

## Plan
- `screens/AUD-06/TrialBalance.tsx`: b's header pill "Draft · Accrued Agent" when every mark is
  the agent's (outlined ticks, no initials, titled "Accrued Agent"); g's chip "TB: Interim ·
  8/31/2026", one "Interim 8/31/2026" column (no BOY without a prior year); e's area picker;
  `PlannedFacts` for g's entity strip and h's "Hand off to tax…" (disabled, tooltip), both behind
  `PLANNED_VISIBLE`; d already drew the AJE column and tag from data.
- `copy.ts` (handoff words), `artboard.tsx` (passes area and planned facts), fixtures:
  `HARLOW_ENTITIES`, `harlowChecks` ("Balances to 0"), `GRANITE_HAND_OFF`, `OPENS[...].planned`.
- Tests: `States.test.tsx` (b, d, e, g, h and the guards), `Production.test.tsx` (with
  `PLANNED_VISIBLE` false: no strip, no hand-off). No agent-authored text on this screen, so no
  `AgentText` use; agent marks carry the agent's name only.
- `docs/screens/AUD-06.md` states and deviations D6, D7.

## Progress log
- 2026-10-26: built; tests at the end of the wave.
