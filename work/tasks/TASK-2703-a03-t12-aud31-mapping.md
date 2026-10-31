---
id: TASK-2703
title: A-03-T12 AUD-31 single entity, MappingTable kit, AUD-06 by FS line
spec: SPEC-580
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-03
plan_key: A-03-T12
branch: s22-a03-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "AUD-31 f matches the artboard at Tier C with MAPPED 128 of 128 and TB BALANCED 1 of 1
  tie, a'-e' hold Tier D computed styles with no Accept or Request changes control, and AUD-06
  groups Granite Peak's lines by FS line once the set is confirmed."

## Scope
**In**: `MappingTable` kit + specimen; `screens/AUD-31` (f, a′–e′, C-20 states); fixtures
(`seed/aud31.ts`, `scenarios/AUD-31.ts`); gallery; manifest `fixture`; AUD-06 grouping by FS line
(`byFsLine`, scenario `fs_line`); tests; `docs/screens/AUD-31.md` DV-B4–B6.
**Out**: Harlow & Pike multi-entity (A-09); live staleness (A-03-T14); Granite's 128 accounts and
BH FS groupings v1 content (A-03-T16); Tier C/D pixel lock (A-03-T19); the `/group/mapping` route.

## Plan
1. Tests first: `AUD-31.test.tsx` (f tallies, groups, subtotal, row lighting; a′ band + Change
   only; b′ polling; c′ edited marker, confirm dialog + POST hash; e′ banner; C-20), and
   `AUD-06/FsLine.test.tsx` (groups by grouping once confirmed; h unchanged).
2. Build the kit, the screen, the AUD-06 hook. Rollback: revert.

## Progress log
- `2026-10-31` — built; tsc, eslint, prettier clean on the touched files. Tests run at the S22 end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1753 (kit, screen, fixture rows, AUD-06 client-side grouping) | content is A-03-T16's; no browser sums | No |
