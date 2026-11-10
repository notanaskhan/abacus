---
id: TASK-6537
title: "A-07-T34 finish: AUD-23 on the live report"
spec: SPEC-644  # A-07 F5 (docs/plan/epics/A-07.md)
acceptance_criteria: [AC-1]  # no paragraph text is editable as free text; choices only
screens: [AUD-23]
risk_zone: green
status: in-review
branch: s33r-a07-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T34
---

## Objective
AUD-23 reads the live report (A-07-T27's service) outside fixture builds.

## Build
- `screens/AUD-23/LiveReport.tsx`: structure from `GET …/report` choices (Modification Picker,
  the template toggles, going concern locked to AUD-19), the paper from the server's included
  blocks with citation markers, DRAFT until approved; choices post with `seen_version`; a
  modification without the partner's card shows "Decision required" and asks it
  (`…/request-decision`); Generate .docx… through `…/documents`; Approve report only with
  `sign_off.l4` and a host binding SHL-12; Go to issuance & release once approved; a refusal
  shows the server's code.
- `screens/AUD-02/completionLetters.tsx`: the AUD-23 chip opens the live report in every
  non-fixture build; the canvas stays the fixture-mode gallery.
- Test `screens/AUD-23/LiveReport.test.tsx`.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass). Partial: the cockpit host binds no
  SHL-12 yet, so Approve is not drawn there; the Versions/Approvals tabs and the compare drawer
  stay with the canvas until their reads are wired; the letterhead is C11's render.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3137 | AUD-23 live: the canvas stays fixture-only; the live view draws the server's blocks and choices | no |
