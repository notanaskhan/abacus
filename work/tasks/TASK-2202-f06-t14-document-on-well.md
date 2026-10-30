---
id: TASK-2202
title: F-06-T14 T10 DocumentOnWell layout, T10a/b
spec: SPEC-400
acceptance_criteria: [AC-19, AC-21]
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T14
branch: s17-f06-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s17
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The T10 DocumentOnWell template: the 470 structure pane (KV sheet or clause toggles with a
Variables fieldset) beside the 896 paper pane (centred title; Edit, Regenerate…, the approval
HumanAction) whose well centres the 600 paper card; states T10a (drafting) and T10b (draft).

Acceptance: "T10a shows three skeleton paragraphs under a header spinner with no approval control
enabled, and T10b shows the DRAFT watermark at 6 percent ink with citation markers."

## Scope
**In**: `packages/ui/src/templates/document-on-well/` (types, StructurePane, DocumentOnWell,
index, tests); the `document` split preset; the T10 gallery board a/b
(`apps/web/src/gallery/specimens/T10/`); parity entries; Tier D; the T10 walk steps.
**Out**: DocBlocks, approved/locked headers, email (F-06-T15); TPL-10 (F-06-T16); T17's suite;
the T22 lock.

## Context to load
- `docs/plan/epics/F-06.md` §3 Stories 4.1, 4.3, §5.2, §6; `docs/screens/T10.md`
- Handoff `T10 Document on well/` (spec, T10a, T10b); `packages/ui/src/agent-text.tsx`

## Plan
Files: `packages/ui/src/templates/document-on-well/{types.ts,StructurePane.tsx,DocumentOnWell.tsx,index.ts,DocumentOnWell.test.tsx}`; `packages/ui/src/templates/index.ts`; `packages/ui/src/layout/split-presets.ts` (+ its test's width table); `apps/web/src/gallery/specimens/T10/{index.tsx,copy.ts}` and `gallery/specimens/index.ts`; `docs/design/parity-manifest.json`; `apps/web/e2e/visual/tier-d-document.spec.ts`; `apps/web/e2e/specimens/f06-document-on-well.spec.ts`; DECISIONS.md, decision log (DEC-1252), `docs/screens/T10.md`.
Migrations, registry, flags: none. Protected files: none.
Tests: kit Vitest (drafting disables approval with aria-describedby; watermark aria-hidden at
6 %; HumanAction refuses an agent; letter has no agent Drafting; geometry; KV links and empties;
locked read-only), Tier D, the walk with axe.
Rollback: revert the PR; nothing consumes the kit yet.

1. [x] Types and panes. 2. [x] Template on the `document` preset. 3. [x] T10 board a/b.
4. [x] Tests, Tier D, walk, parity entries. 5. [ ] End review run.

Tests (mapped to ACs): AC-19 → `DocumentOnWell.test.tsx` "T10a"/"T10b", `test_ac19_*` in the walk;
AC-21 → "Approve only calls onApprove", "an agent actor never gets…", `test_ac21_*`.

## Progress log
- `2026-10-29` — Built on `s17-f06-t14` (build-only; tests run at the S17 end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1252 | drafting draws disabled controls (testable INV-1), board data, `document` preset, fonts in the consumer chunk | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; F-06-T15 adds DocBlocks and the c–e states.
