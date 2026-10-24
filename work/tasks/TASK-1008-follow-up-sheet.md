---
id: TASK-1008
title: Follow-up sheet for BND-01 b and BND-02 d; fixture-to-live swap for BND-01, BND-02 and SHL-14 (P-06-T16)
spec: SPEC-319
acceptance_criteria: [AC-16, AC-18]
risk_zone: green
status: in-progress
epic: P-06
plan_key: P-06-T16
branch: s6-follow-ups
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"On staging Grace sends a drafted follow-up and the audit log shows Grace, not the agent, as sender." Screens BND-01 (b) and BND-02 (d); contracts `docs/screens/BND-01.md`, `BND-02.md`; C5 v1.2 §12.

## Scope
- `domain/requests/followUps.ts` (generated client: draft, edit, send several with an Idempotency-Key, Undo) and `FollowUpSheet.tsx` (O3, BND-04 c's wording; DEC-222).
- BND-01: artboard b (Client activity │ None in 30 days, Fenwick selected), "Send reminder(s)…" in the pane header, filters mirrored in the URL (DV-15).
- BND-02: "Send reminder…" (open items) and the dock's "Send reminder for this request" open the sheet.
- Live swap: the screens read only the generated client; binder rows and records carry `follow_up.draft`/`follow_up.send` in `allowed_actions` (backend, requests).
- Fixtures: `fixtures/handlers/follow-ups.ts`; BND-01 b and BND-02 d drafts from BND-04 c.

## Progress log
- 2026-10-24: built. `pnpm -C apps/web vitest run`: 132 files, 1,356 tests pass (BND-01 25 → 27 incl. b, the sheet, Edit, the URL; BND-02 22). `tsc --noEmit` clean.
- Not done here (needs staging): walking Grace's send on staging and reading the audit log; the manifest stays `fixture` for BND-01 and `planned` for BND-02 until then. Staging also needs the Reminder template imported (`POST /v1/platform/email-templates/import`, key `notification.follow_up_sent`) and `binders.engine` on for Brightwater Hale. SHL-14 needed no change for the swap (it already reads the generated client).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-222 | The follow-up sheet's design source, BND-01 b without a bulk bar, capabilities from allowed_actions, the URL mirror | No |
