---
id: TASK-2401
title: P-04-T48 SHL-12 Sign-off modal, frames a, a′, b, c, d, e, g, h
spec: SPEC-360
acceptance_criteria: [P-04-T48]
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T48
branch: s19-p04-t48
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
SHL-12, the O3 sheet at `?ov=signoff:<targetType>:<targetId>[:<level>]` that records an immutable
sign-off: the workpaper card with version and content hash, the level picker limited to the
allowed levels, the L1–L5 ladder with the performed-and-adopted line, the checks, the statement,
View changes and Re-sign, the EQR single option and the tax final-approval variant.

Acceptance: "Each blocked frame names its reason in words, a-prime shows the MD and HL ticks, and h
keeps Resolve 11 issues to approve disabled."

## Scope
**In**: `apps/web/src/screens/SHL-12/` (SignOffSheet, SignOffChips, copy, scenarios, test);
`apps/web/src/domain/review/signoffs.ts`; the `signoff` overlay registration; the SHL-12 gallery
artboard; the SHL-12 fixtures' missing reads (seed/review.ts) and `fixtures/scenarios/SHL-12.ts`;
HumanAction's optional whole `label`.
**Out**: bulk (f, P-04-T49); live consumers (A-04 workpapers, T-02/T-04 final approval); the
`review.sign_offs` flag (with the first live consumer); manifest status (stays `planned` until
links are wired).

## Plan (amber)
Files: as in Scope, plus `routes/firm/sheets.tsx`, `routes/firm/sheets-host.tsx`,
`screens/gallery.tsx`, `domain/review/index.ts`, decision log (DEC-1451).
Migrations: none. Registry and flags: none (behind `review.grammar_api`, as SHL-10). Protected
files: none.
Tests: `SHL-12.test.tsx` — one per frame; a → a′ write body (hash + statement seen) and toast;
blocked frames' CTA disabled and described by the failing check's words; h disabled and no write on
click; no agent control. Contract test `fixtures/contracts/review-grammar.test.ts` still types the
fixtures.
Rollback: revert the PR; the overlay key is new and nothing opens it in production (flag off).

1. [x] Fixtures. 2. [x] Domain hooks. 3. [x] Sheet and chips. 4. [x] Overlay and gallery.
5. [x] Tests. 6. [ ] End review run.

## Progress log
- `2026-10-30` — Built on `s19-p04-t48` (build-only; tests run at the S19 end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1451 | words from facts, HumanAction whole label, h on the return, deferred banner/note fields | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; P-04-T49 adds bulk (f).
