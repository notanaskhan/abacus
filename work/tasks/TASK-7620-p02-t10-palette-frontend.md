---
id: TASK-7620
title: P-02-T10 palette frontend (SHL-02 "Go…" on the O5 frame)
plan_key: P-02-T10
spec: SPEC-000  # docs/screens/SHL-02.md; C15 v1
acceptance_criteria: [AC-1]  # keyboard and screen-reader paths in every state; planned targets hidden in production; focus returns to Go… on close
risk_zone: green
status: in-review
branch: p02-t10-palette
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
SHL-02 "Go…": the firm palette over C15 v1, wired to Go… and ⌘K / Ctrl+K behind `search.palette`.

## Plan
- `packages/ui/src/overlays/palette.tsx` (additive): `variant="go"` (640 wide, top 88, rows 40,
  group labels 28, footer 36), row `context`, `ranges` (matched words at 500), `status`,
  `runNewTab` (⌘↵ / Ctrl+↵ keeps the palette open), `title`, footer `hints`, a polite `liveText`.
  The `frame` variant (F-05-T20, the interim Go…) is unchanged.
- `apps/web/src/domain/search/` (new): `useFirmSearch` (debounced 150 ms, aborted by the query's
  signal, text only in the POST body), `useRecents`, `useRecordRecent`.
- `apps/web/src/screens/SHL-02/` (new): `Go` (groups in canonical order, C2 status words via
  `registryWord`, Recent and Create with nothing typed, `>` agent mode behind
  `search.agent_mode`, the empty state and the visible-only suggestion, the error words, planned
  targets hidden in production by `PLANNED_VISIBLE`), `copy.ts`, `scenarios.ts`, `SHL-02.test.tsx`.
- `shell/firm/ToolbarData.tsx`: SHL-02 replaces the interim Go… while `search.palette` is on.
- Rollback: revert; the flag is off and the interim frame stays.

## Deviations (DEC-4615)
- Create and Actions come from the screen's copy with their manifest screens (hidden when planned
  in production), not from a manifest-wide action registry; `useCan` gating per action waits for
  each target's route (the server refuses anything not allowed in any case).
- SHL-02 stays `planned` in the manifest: its rows open through the manifest's paths, not
  `to.<ID>()` builders, so the link-contract wiring lands with P-02-T12's journeys.
- The context-bound Actions of a (Run an agent on…, Message…, New to-do on…) are not built here.

## Progress log
- `2026-11-12` — Palette built (DEC-4615). Tests at the S40 end pass.
