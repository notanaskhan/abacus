---
id: TASK-6529
title: "A-07-T34: AUD-23 Report builder in fixture mode on T10"
spec: SPEC-644  # A-07 F5 (docs/plan/epics/A-07.md)
acceptance_criteria: [AC-1]  # the row's acceptance (Objective)
screens: [AUD-23]
risk_zone: green
status: in-review
branch: s33-a07-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: A-07-T34
---

## Objective
All ten AUD-23 artboards render from fixtures and no paragraph text is editable as free text.

## Build
- `apps/web/src/screens/AUD-23/` (`copy.ts` verbatim from the handoff canvas `#aud23`, spec and
  revision R2; `ReportBuilder.tsx`; `index.tsx`; `AUD-23.test.tsx`).
- Structure 470: Engagement, Opinion (Conclusion/Report by mode), Paragraphs, Dates & signature,
  Approvals with Generated documents. Modification picker records a version; a modification
  shows "Decision required" and "Request partner decision…" (SHL-11, `onRequestDecision`) and
  disables approval. EOM/OM toggles with the O1 reason-code popover; going concern, ERISA
  supplemental, other information and legal/regulatory are fixed (AUD-19, AU-C 703, AU-C 720).
- Paper 600: letterhead, sections that fade over 220 ms, citation markers [1]-[3] lighting their
  rows, Show full paragraph, DRAFT watermark until approval, signature placeholder until release.
- Header: Edit (explains the text comes from the choices; never free text), Compare v1
  (`onCompare`, SHL-16), Generate .docx… (O3 sheet: template, version, locked DRAFT, signature
  placeholder, deterministic-render helper), Approve report only with `canApprove` (`sign_off.l4`;
  SHL-12 via `onApprove`), Go to issuance & release once approved. No Release control.
- Tabs Report · Versions n · Approvals. States a-j. Opened inside the AUD-02 cockpit from the
  AUD-19 "AUD-23" chip in fixture mode (`completionLetters.tsx`).

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). Partial: fixture mode only (the live
  read of A-07-T27's `GET …/report` and the SHL-12/SHL-11/SHL-16 hosts bind with the live swap);
  the version-row attribution keeps the canvas's "Accrued Agent" words for v1 (DEC-3129).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3129 | AUD-23 in fixture mode: copy from the canvas, choices only, the partner's approval bound by the host | no |
