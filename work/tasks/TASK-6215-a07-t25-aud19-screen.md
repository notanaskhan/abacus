---
id: TASK-6215
title: A-07-T25 AUD-19 Completion in fixture mode
spec: SPEC-644
acceptance_criteria: [AC-1]  # seven artboards from fixtures; "12 of 17" with N/A excluded
risk_zone: green
status: in-review
epic: A-07
plan_key: A-07-T25
branch: s31-a07-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- Screen `apps/web/src/screens/AUD-19/` (`useCompletionCanvas`, copy verbatim from the handoff):
  segmented Checklist · Subsequent events · Legal letters · Going concern; summary pills and
  "12 of 17"; "What blocks the report" with gate tags, link chips and due dates; the checklist
  table with discs, evidence and link chips; Sign off… to SHL-12; the read-only going-concern
  card; All clear to AUD-24. Composed in AUD-02 as `completion_checklist`.
- Fixtures (`fixtures/seed/audit-completion.ts`): the 18 handoff items, subsequent events, legal
  letters, going concern (Northwind and Granite Peak), runs #4231 and #4240 for the dock;
  scenario clocks and viewers as the screen contract.
- Test `screens/AUD-19/AUD-19.test.tsx` (run at the S31 end pass).

## Partial (DV-AUD-19-2 to 5)
- Blocker sentences, the summary's run line, Granite's question wording; live reads wait for
  A-07-T47.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2815 | AUD-19 in the cockpit on the projector's counts; read-only going-concern card | no |

## Progress log
- 2026-11-08: built; tests written, run at the S31 end pass.
