---
id: TASK-7926
title: "W-02-T16 rest: WB-02's Internal Control link opens AUD-09"
plan_key: W-02-T16
spec: SPEC-653
acceptance_criteria: [AC-A2]
risk_zone: green
status: in-review
branch: w02-t16-aud09-nav
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish W-02-T16's partial: the answer's Internal Control link navigates to AUD-09 (`/audits/$auditId/controls?sheet=internal-control`) for the audit the answer names.

## Done
- `answerOf` reads the audit from the answer blocks' first `entity_ref` with record type `audit` (`controlAuditId`); the link shows for it or for a stored `links` part.
- `onOpenControl(auditId)`; `routes/firm/workbench.tsx` navigates with `to.AUD09` and `sheet: internal-control` (nothing when the answer names no audit).
- Tests: e passes the audit id; `answerOf` takes it from `entity_ref`; an answer with no ref shows no link.

## Partial
- WB-03's thread answers use W-02-T17's renderer (S43); the same callback lands there.
- Closed by S43 (2026-11-14, main 322ca3310): W-02-T21 (#1977): WB-03's thread answers use W-02-T17's renderer.

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4923 The Internal Control link's target is the answer's `entity_ref` (record type `audit`), not a new link part | AgentBlocks already carries entity refs; no new C6 part | no |
