---
id: TASK-2529
title: N-02-T37 ENG-04 part 2 (d, e, f, Compare to standard, Send into SIG-02)
spec: SPEC-381  # AC-13..AC-15; docs/screens/ENG-04.md
acceptance_criteria: [AC-13, AC-14, AC-15]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T37
branch: s20c-n02-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
ENG-04 part 2: d signed and locked (Copperleaf, approver of record, SSARS routing note, Amend
addendum), e audit variant (Fairhaven, AU-C 210 clauses, 103(a)(3)(C) election), f bundled
consents as two document tabs (Feld), Compare to standard redline overlay over C11 compare,
Request partner approval and Send for signature into SIG-02 prefilled with the toast "Sent to Owen
Calder · E13"; fixture-to-live on staging.

Acceptance (backlog row): "Scenario tests for d, e and f pass and on staging the Ridgeline letter
moves Draft to Partner approved…"

## Plan (green)
- Contract: additive composer fields (`signed_on`, `sent_at`, `routing_note`, `documents`); `make generate`.
- Fixtures d–f (`seed/letters.ts`, `scenarios/ENG-04.ts`), C11 compare fixture.
- Screen: d/e/f rendering, document tabs, the redline overlay; ENG-02 wires Send to SIG-02.
- Tests: d, e, f and compare scenarios.

## Notes
- Staging live swap not done: the letter routes are 501 stubs (N-02-T35); recorded in DEC-1574.

## Progress log
- `2026-10-31` — Built on `s20c-n02-t37` off main. ENG-04 13 passed, ENG-02 green.
