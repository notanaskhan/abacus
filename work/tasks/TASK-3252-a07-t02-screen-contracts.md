---
id: TASK-3252
title: A-07-T02 screen contracts AUD-18, AUD-19, AUD-21 to AUD-25 (49 artboards)
spec: SPEC-644
acceptance_criteria: [AC-2]
risk_zone: green
status: in-review
epic: A-07
plan_key: A-07-T02
branch: s27-a07-t02
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Every artboard letter is marked live, fixture-only or deferred with its owning epic, and the
link-contract test knows every outbound target."

## Plan
- `docs/screens/{AUD-18,AUD-19,AUD-21,AUD-22,AUD-23,AUD-24,AUD-25}.md` in the AUD-09 layout:
  route, template, handoff folder, tasks; 49 artboards post-revision (AUD-23 h–j, AUD-25 R2) with
  persona, demo clock (CDT/CST), snapshot, condition and status; API from the T04/T05 stubs;
  status objects; copy; deviations DV-1 to DV-9; every outbound link of `handoff-links.json`
  with its owning epic.
- Generated once from the epic's §2.1 artboard table and the link graph by a scratch script
  (not committed); the documents are the source from here on.
- Test: `apps/web/src/routes/a07-screen-contracts.test.ts`.

## Progress log
- 2026-11-04: built. AUD-23 g is the only fixture-only artboard (DV-9).

## Decisions made during this task
None new (DV-1 to DV-9 from A-07 §2.4).
