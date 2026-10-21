---
id: TASK-351
title: "F-05-T19 · View states and feedback: ViewState, EmptyState, Skeleton, ErrorRow, OfflineBanner, AgentRunningRow, restricted and flag-off, C-19 progress tiles"
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: in-review
epic: F-05
plan_key: F-05-T19
branch: worktree-agent-a4ccf31609bc9134e
worktree: agent-a4ccf31609bc9134e
created: 2026-10-21
updated: 2026-10-21
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Frontend only: no endpoint, no migration, no dependency. Tokens only; no raw hex; sample names are the handoff's, kept in the specimens.
> - Do not edit the shell components (AppShell, Toolbar, RecordHeader, Pane): another task builds them.

## Objective

Give every template one `ViewState` and the feedback components to draw it: loading, empty, filtered-empty, error, restricted and flag-off keep the pane's header and row heights, restricted shows no record data, and a switched-off module is a designed state, never a 404; plus the C-19 progress tiles.

## Scope

**In**
- `packages/ui/src/components/states.tsx` (C-20): `EmptyState` (upgraded in place), `EmptyLink`, `ErrorState`, `Skeleton` and `SkeletonRows` (list, table, tasks, chat, card), `ErrorRow`, `WaitingBadge`, `AgentRunningRow`, `AgentLive`, `OfflineBanner` with `useOnline`, `FieldsetEmpty`, `runRowView`, `STATE_GEOMETRY`, `STATE_COPY`.
- `packages/ui/src/components/view-state.tsx`: the plan's `ViewState`, `ViewStateBody` (header and column heads stay; only `ready` renders children, which may be a function), `RestrictedState` with `RESTRICTED_COPY`, `FlagOffState` (the T21e grammar).
- `packages/ui/src/components/progress.tsx` and `progress-model.ts` (C-19): `ProgressBar`, `RatioStat`, `UploadRing`, `StepCounter`, `KpiTile` and `KpiGrid`, `StatusTile` and `StatusTileStrip`, with the pure helpers (`barView`, `ringView`, `stepViews`, `kpiDelta`, `sparkPoints`, `practiceOpen`). `DoneCount` was already in the Pill family.
- `motion.css`: `ac-slide` and `motion-slide` for the indeterminate bar; `--animate-pulse` set to the kit's pulse.
- Specimens in `/components`: `c-20-view-states`, `c-20-forced-states`, `c-20-empty-state`, `c-20-skeleton`, `c-20-agent-running-row`, `c-20-offline-banner`, `c-20-restricted`, `c-20-flag-off`, `c-19-progress-bar`, `c-19-ratio-stat`, `c-19-upload-ring`, `c-19-step-counter`, `c-19-kpi-tile`, `c-19-status-tile`.
- 25 conflicts between the bundles, the AA ladder and the plan, one line each, in `tokens/DECISIONS.md` under "View states and progress (F-05-T19)".

**Out**
- The pane header and the Pane, AppShell, Toolbar and RecordHeader (the shell task). The pane in the specimens is local to them.
- `FeatureGate`, `useFlag` and `useCan` (they take the flag-off state as their fallback; a later task).
- C-26 `AgentProgress` (P-09). `AgentRunningRow` follows its rules for attribution ("‹person› via Agent") and for never drawing a failed run as progress.
- The copy registry (F-05-T32): the restricted lines are inferred and live in `RESTRICTED_COPY` until it takes them over.

## EmptyState callers

`EmptyState` keeps its name, its export from `@abacus/ui` and `title`, `children` and `action`. No caller changed. The 30 call sites in `apps/web/src` compile and pass unchanged; the layout moved to the bundle's (centred in a `flex-1` body, 320 max, tile, 14/500 title). `Skeleton` keeps `className` sizing; it now waits 200ms and pulses on the kit's rhythm, so the four older tests that look for `.animate-pulse` still pass without edits.

## Plan

Green zone. Order: pure helpers and their tests, the components, the specimens, the DECISIONS lines, the tests for heights and restricted, then the checks.

Files: `packages/ui/src/components/{states,view-state,progress,progress-model}.ts(x)` and tests, `packages/ui/src/specimens/{states,progress}.tsx`, `specimens/index.ts`, `index.ts`, `surfaces.tsx` (re-exports), `motion.css`, `tokens/DECISIONS.md`, `apps/web/e2e/components.spec.ts`.

Tests: `states.test.tsx`, `view-state.test.tsx`, `progress.test.tsx`, `progress-model.test.ts`; Playwright `view states` in `components.spec.ts`.

## Definition of done

- [x] Each ViewState kind renders with the header and row heights unchanged: `view-state.test.tsx` (the header node is never replaced, the heights read 46, 30, 48, 40 and 50 in every kind and mode) and the Playwright test that measures the real layout of the Files and Sessions panes across Loaded, Loading, Empty and Error.
- [x] Restricted shows no record data: the body never calls its children, for every reason, in unit and in the gallery; the copy never names a wall.
- [x] Flag-off is a designed state, never a 404: the T21e line inside the route's frame, no 404 wording, no blank body.
- [x] Reduced motion: nothing animates (tests render each component under the preference and find no `motion-`, `animate-` or `transition-` class and no animation delay; the existing `getAnimations()` check over `/components` passes).
- [x] The Agent is "Accrued Agent" in every string; no persona, no "!", no "...", no emoji.
- [x] `pnpm -C packages/ui test`, `pnpm -C apps/web exec vitest run`, tsc and lint for both.
- [x] `make check-fast` (see the log).
- [ ] `make check` stage 2 was not run: nothing here touches the backend.

## New dependencies

None.

## Progress log

- `2026-10-21` Built the C-20 and C-19 components, `ViewState`, the specimens and the tests; read the C-20, C-19 and C-26 bundles and `kits.md`; looked at the T21e, T21f and ATT-01f screenshots for the flag-off and restricted grammar.
- `2026-10-21` Checks: `pnpm -C packages/ui test` 568 passed (about 140 new); `pnpm -C apps/web exec vitest run` 695 passed; tsc and eslint clean for both; Playwright `components` on a fixtures gallery server 13 passed (axe on `/components/**`, the reduced-motion check, the new heights and restricted tests).
- `2026-10-21` Gotcha: `.animate-pulse` is what four older screen tests look for in a loading state. Rather than edit them, `Skeleton` takes that class and `--animate-pulse` is the kit's pulse.
- `2026-10-21` Gotcha: axe failed `color-contrast` on the KPI tiles because they were mid-rise (opacity from 0) when the page was checked. The specimen draws them still and rises them on Replay.
- `2026-10-21` Gotcha: `toFixed` is banned in the package (format.ts only), so the sparkline's points go through `ratio()`.
- `2026-10-21` Gotcha: `aria-label` on a `section` makes it a landmark, and axe wants unique landmark names; the specimen panes are `role="group"`.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|
| `ViewStateBody` takes `children` as a node or a function, and calls the function only for `ready` | Restricted must never build record data | no |
| The pane header is the caller's; `StatesPane` and its toggle are specimens | The shell is another task; the toggle is a preview control | no |
| Heights are `STATE_GEOMETRY` and applied inline to rows | One number for the loaded row and its skeleton, and a jsdom test can read it | no |
| Restricted lines are inferred, `walled` does not say "wall" | DEC-43 gives a walled record 404 semantics | no |
| The rest are in `tokens/DECISIONS.md`, "View states and progress (F-05-T19)" | One line each | no |

## Gotchas and discoveries

- `format.ratio()` is a decimal, not the bundle's `ratio()`; the bundle's is `format.progress()`.
- `tailwind-merge` drops `leading-*` when it follows a type role of the same list, so write the role first (`text-dashboard leading-[1.1]`).

## Questions for the human

- [ ] The handoff's C-20 error line says "Accrued could not reach the server" and the Agent's empty copy says "the agent". The firm app keeps the first as written; the portal drops the name; "Accrued Agent" replaces the second. Confirm.

## Handoff

- **Current state:** built, tested and checked; committed on this branch, not pushed.
- **Exact next step:** the shell task mounts `OfflineBanner` under the Toolbar and `AgentLive` in the Pane header; T28 (IndexList) takes `ViewStateBody` and `StatusTileStrip`.
- **Known failing checks:** none.
