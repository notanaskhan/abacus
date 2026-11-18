---
id: TASK-8545
title: "A-08-T32: AUD-14 live on the confirmations reads"
spec: SPEC-657
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
branch: a08-t32-aud14-live
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-18
updated: 2026-11-18
plan_key: A-08-T32
---

## Objective
AUD-14 fixture-to-live: the log, coverage line and drawer on the generated client; manifest link planned to live.

## Plan (green)
1. screens/AUD-14/live.tsx: AUD14Live on listConfirmations, confirmationSummary and getConfirmation; logRowOf maps an API row to the log (type label, address check 'method (initials, date)', channel label, short dates, No response with Viewed / 2nd request sub-lines; book, confirmed and difference as the server answers them); Book → SHL-09 (confirmation, book_total)
2. screens/AUD-14/index.tsx: ConfirmationsWorkspace takes an optional live data prop (rows, coverage, the open row's detail, selection, onBook); fixture states unchanged
3. Route /audits/$auditId/confirmations (audits.cockpit gate); manifest AUD-14 live with its path
4. Tests: live.test.ts (3); link-contract rule 1 (AUD-14 → SHL-09 wired)

## Progress log
- `2026-11-18` — Built 2026-11-18 (S49 open rows, round 2). Not done: the staging run against the scenario (needs staging). The mail channel's label 'Mail' is undesigned (DEC-5530). Gates and tests run once at the S49 open-rows end pass (build first, test last).
- `2026-11-18` — End pass: the client note named Brightwater Hale and Granite Peak in copy, which the live route carried into the production build (dist test). Now `clientNote(firm, client)` with the fixture names in `fixture-note.ts` (gallery and tests only). Live shows no note until a client-name read reaches the confirmations workspace (open).
