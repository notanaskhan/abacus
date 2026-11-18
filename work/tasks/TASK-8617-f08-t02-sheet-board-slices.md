---
id: TASK-8617
title: "F-08-T02: Seed slices: Granite Peak BH-FS-430 SURL sheet and the Sep 24 audit-program board"
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: f08-t02-sheet-board-slices
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: F-08-T02
---

## Objective
Spec section: docs/plan/epics/F-08.md §2 (TPL-20, TPL-21), §5 fixture scenarios, G1. Typed seed slices against draft contract types; fixture personas cole-hart and simone-baptiste.

## Plan (green)
1. apps/web/src/fixtures/contracts/{sheets,board}.ts: draft view-model types (deleted when K-03/K-04 contracts land).
2. apps/web/src/fixtures/seed/granite-peak-fy2026-surl-sheet.ts: SURL-01..14 field for field from the SHT-01 handoff; SURL-15..40 as derived counts and totals only (DF-35).
3. apps/web/src/fixtures/seed/granite-peak-fy2026-board.ts: the 13 TPL-21 cards with owners, metrics, overlays and sign-off slots; the BH-FS-430 move.
4. granite-peak-fy2026.foot.test.ts: 3,286,400 = 1,942,600 + 1,343,800; one exception SURL-05; columns 4-5-2-2 then 3-6-2-2 with sign-offs unchanged; binder 12/10 of 21; cole-hart and simone-baptiste slugs.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5617). Found: Cole Hart and Simone Baptiste are already seats in fixtures/seed/people.ts, so ?as= resolves without a new persona. Slices sit in the seed root (the lint rule refuses ../../ imports from a subfolder), not seed/granite-peak-fy2026/. Not run: vitest at the end pass. Gates and tests run once at the S50 end pass (build first, test last).
