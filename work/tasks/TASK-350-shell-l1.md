---
id: TASK-350
title: "F-05-T18: Shell L1 — AppShell, Toolbar with measured nav overflow, RecordHeader, Tabsbar, Pane and PaneHeader, Timeline"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-5, AC-6]
risk_zone: green
status: in-review
epic: F-05
plan_key: F-05-T18
branch: worktree-agent-a628e832277000569
worktree: agent-a628e832277000569
created: 2026-10-21
updated: 2026-10-21
---

> **Rules for the agent working this task**
>
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - `packages/ui` imports nothing from `apps/web`. The nav list is a prop.
> - Frontend rules: tokens only, no raw hex, Geist 400 and 500, controls are pills (DEC-124). The firm app shows no Accrued mark; the portal shows it only in the firm-enabled footer.
> - No push, no CI. Holding this for the batch.

## Objective

Build the C-00 shell in `packages/ui` so every later screen composes AppShell, RecordHeader, Tabsbar and Panes without new chrome, and prove the toolbar's DF-39 fallback order at 1280, 1400 and 1440 and the Tier D heights 46 / 42 / 59 / 46.

## Scope

**In** (`packages/ui/src/layout/`, exported from the package root)

- `AppShell` (firm, portal, framed): toolbar, record header, tabsbar, the body row (gap 10, padding 10 12 12), the portal footer when the firm turns it on, an `overlay` slot for the command palette, Ctrl or Cmd K to `onGo` (firm only). It takes the nav items as props.
- `Toolbar` (firm, 46) with measured nav overflow: `nav-overflow.ts` is pure (`fitNav`, `fitToolbar`); the component measures a hidden row at weight 500 and re-fits on resize, on fonts ready and on every render. `PortalToolbar` and `PortalFooter` (46, white-labelled).
- `RecordHeader` variants `default` (42, with the registry's sync chip), `audit` (59, with the Auto mode switch), `close` (42 + 50) and `settings` (42).
- `Tabsbar` (50 / 44 / 60) holding the C-05 Segmented and ViewToggle.
- `Pane`, `PaneHeader` (46), `PaneAction` (icon, round, pill, picker, meta), `FooterAction`, `FooterSpacer`.
- `Timeline` (the C-23 Activity list).
- Specimens in `/components` for every part and width (`specimens/shell.tsx`, registered in `specimens/index.ts`).
- Tier D rows in `apps/web/e2e/visual/tier-d.spec.ts`: the heights, the pane title type, and the toolbar at 1440, 1400, 1280 and 1080.

**Out**

- The command palette (O5, F-05-T20), SplitLayout and its presets (F-05-T29), PortalLayout, MobileTabBar and PortalBrand (F-05-T35), the `?ov=` codec.
- **Adopting AppShell in the live apps/web shell.** Not done: see the decisions.

## Context to load

- `docs/plan/epics/F-05.md` section 9 (F-05-T18), `docs/plan/04-frontend-architecture.md` sections 3.11 and 5, DF-39 in `docs/plan/09-decisions-adrs.md`.
- The C-00 bundle (`specs/01` to `06`, `reference/overflow-fit.ts`, the screenshots), SHL-01 (`spec.md`), C-23 (Activity), TPL-12 (the settings subbar).
- `packages/ui/src/tokens/DECISIONS.md`, "Shell L1 (F-05-T18)": every conflict is one line there.

## Plan

Green zone: no migration, no dependency, no API change. Rollback is a revert.

1. [x] `layout/nav-overflow.ts`: the bundle's `fitNav`, and `fitToolbar`, the DF-39 ladder over measured widths (none, short firm name, house pill, Signatures in More, Signatures + Closes + Audits in More, then a trailing run at a time).
2. [x] `layout/toolbar.tsx`: the controls, the hidden measuring row, the More menu on the existing `Menu`, the Go… tooltip on the existing `Tooltip`.
3. [x] `layout/record-header.tsx`, `tabsbar.tsx`, `pane.tsx`, `timeline.tsx`, `portal-toolbar.tsx`, `app-shell.tsx`, `index.ts`; the root export.
4. [x] Specimens and their registry entries.
5. [x] Tests: `layout/nav-overflow.test.ts`, `layout/shell.test.tsx`; Tier D in the visual project.
6. [x] Decisions in `tokens/DECISIONS.md`.

Tests (mapped to the acceptance string and the spec):

- "Toolbar specimens at 1280, 1400 and 1440 apply the DF-39 fallback order" → `nav-overflow.test.ts` (the order, every step visited, the boundaries from the measured widths) and `shell.test.tsx` "Toolbar: DF-39 at 1440, 1400 and 1280" (mocked element widths, re-fit on resize); `tier-d.spec.ts` "the toolbar at 1440 / 1400 / 1280 / 1080" in a real browser.
- "nav type never shrinks or wraps" → `shell.test.tsx` "the nav never wraps and never shrinks its type" (13.5px role, `whitespace-nowrap`, `flex-none`, at seven widths) and the Tier D check (computed 13.5px, 32px, `nowrap`, the nav never overflows its space).
- "Tier D heights 46/42/59/46 hold" → `shell.test.tsx` "shell heights" (the `root.css` tokens, and each part built on its token) and `tier-d.spec.ts` (computed heights: toolbar 46, portal toolbar 46, record header 42 / 59 / 42 + 50 / 42, pane header 46, tabsbars 50 / 44 / 60).
- SPEC-048 AC-3 → axe over `/components` (run once in the visual project): no serious or critical finding.

## Definition of done

- [x] `pnpm -C packages/ui test`: 560 passed (76 new).
- [x] `pnpm -C apps/web exec vitest run`.
- [x] tsc and lint for both.
- [x] `pnpm visual` Tier D rows (27 tests, the 15.6px line stays the existing expected failure).
- [x] `make check-fast`.
- [ ] Not pushed, no CI run.

## New dependencies

None.

## Progress log

- `2026-10-21` Built the layout parts, the specimens, the tests, the Tier D rows and the decision lines. Measured with Geist at weight 500: nav items sum to 1016px with gaps; the steps change at bar widths 1405 (none), 1374, 1351, 1329 and 1197.
- `2026-10-21` Checks: `pnpm -C packages/ui test` 560 passed; `pnpm -C apps/web exec vitest run` 695 passed; tsc and eslint clean for both; `pnpm visual` tier-d 27 run (the existing 15.6px expected failure aside, all pass); axe over `/components` found nothing serious; `make check-fast` passed (firm initial JS 224.1 KB of 250).

## Decisions made during this task

| Decision | Reason | Needs ADR? |
| --- | --- | --- |
| The live apps/web shell is left alone | `screens/Layout.tsx` (231 lines) is the rail layout with the sign-in guard, the firm chooser, the notification drawer and the palette wired through it, and its tests assert that structure; a swap is F-05-T23's legacy re-skin, which also moves the 51 screens and retires `ClientBell` | no |
| All DF-39 steps are automatic, in order | SHL-01 and DF-39 over the bundle, which makes only the More step automatic; see DECISIONS.md | no |
| Fallback 1 shows a shorter name | "Brightwater Hale" is about 110px, so capping the label at 140 changes nothing | no |
| Slots, not action arrays, for Pane, PaneHeader and RecordHeader | Plan 04 4.5 rule 5 | no |
| The Secured by footer is off by default | The plan makes it a firm toggle (ADM-10) | no |

The rest are one line each in `packages/ui/src/tokens/DECISIONS.md` under "Shell L1 (F-05-T18)".

## Gotchas and discoveries

- The bundle's nav-width numbers (about 1018px of labels, 996px of space at 1400) are close to what Geist measures here: 1016px of labels, and the bar needs 1405px with the full firm name. At 1440 everything fits; at 1400 the short firm name is enough; 1280 needs Signatures, Closes and Audits in More.
- A label's weight changes its width. The active item is 500, so each label carries a hidden 500 copy of itself (`after:content-[attr(data-label)]`) and measures at 500; without it the active item shifts its neighbours.
- jsdom has no layout, so the toolbar tests mock `getBoundingClientRect` by `data-measure` key and call the stubbed ResizeObserver's callback to resize. Real widths are asserted in the visual project.
- The tooltip and menu held open for a specimen are drawn in place, so a strip that shows one needs room under it (`room` on the specimen's `Strip`) or its scroll box clips it.

## Questions for the human

- [ ] None.

## Handoff

Done apart from the final check run and the commit; see the progress log. F-05-T20 should settle the palette's width (640 in `CommandPalette`, 560 in the C-00 bundle) and take `AppShell`'s `overlay` slot. F-05-T23 adopts `AppShell` in apps/web.
