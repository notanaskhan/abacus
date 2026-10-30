---
id: TASK-2326
title: F-06-T15 T10 DocBlocks renderer
spec: SPEC-400
acceptance_criteria: [AC-19, AC-21]
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T15
branch: s18-f06-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
T10 DocBlocks over P-24 segments (heading, paragraph with citations and the edit mark, statement
table, bullets, letterhead, signature), CiteMarker lighting, Approved and Locked states (T10c,
T10d), the email variant at 600 and 390; agent prose only on the internal paper while P-25 is off.

## Plan
- `DocBlocks.tsx` (+ `EmailFrame`, `agentAllowed`), DocumentOnWell T10c/T10d, exports; DEC-1372.
- Test: `DocBlocks.test.tsx` (10; the kit's 20 pass with jsdom).

## Progress log
- `2026-10-30` — built; vitest (jsdom), tsc, eslint, prettier run once. `[skip ci]`.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** F-06-T16 TPL-10 specimens (stacked on this).
