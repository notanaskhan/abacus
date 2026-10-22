---
id: TASK-354
title: "F-05-T20 · Overlay stack E3, O1 to O6: OverlayStack, Popover, Drawer, SheetModal, FullSheet, CommandPalette, Wizard, Dialog sizes, ConfirmDialog, scrims, ?ov= codec and OverlayHost"
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: amber
status: in-review
epic: F-05
plan_key: F-05-T20
branch: worktree-agent-a57b8cced2a025348
worktree: agent-a57b8cced2a025348
created: 2026-10-22
updated: 2026-10-22
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Frontend only: no endpoint, no migration, no dependency. Tokens only; no raw hex; sample names are the handoff's, kept in the specimens.
> - Do not build toasts (F-05-T21) or the independent tests (F-05-T22). Do not change `toast.tsx` or the screens under `apps/web/src/screens`: another builder is editing them.

## Objective

Give every overlay one behaviour: an OverlayStack that makes Escape close only the topmost layer, returns focus to the opener, never opens two drawers and asks "Discard changes?" before a dirty layer closes, with the O1 to O6 layers and the C-22 dialogs built on it, and the `?ov=` codec and OverlayHost that make a layer deep-link, survive a reload and close on Back.

## Scope

**In**
- `packages/ui/src/overlays/`: `stack.ts` (the store, focus return), `stack-react.tsx` (provider, `useOverlayLayer`, z-order), `frame.tsx` (scrim, title, close, initial focus), `layer.tsx` (one modal layer), `confirm.tsx` (`ConfirmDialog`, `DiscardGuard`), `dialog.tsx` (sizes sm 420, md 560, lg 760, xl 1140), `drawer.tsx` (O2 modal and peek, `DrawerCard`), `sheet.tsx` (`SheetModal` O3, `FullSheet` O4 with `SheetColumns`), `popover.tsx` (O1 card and tray), `palette.tsx` (O5), `wizard.tsx` (O6 frame), `index.ts`.
- `components/popover.tsx`: `Popover` moved out; `Menu` joins the stack (Escape closes it before the dialog it is in, and it sits above that dialog). `Tooltip` untouched.
- `components/dialog.tsx`, `components/overlays.tsx`, `components/command-palette.tsx` removed; `index.ts` re-exports from `overlays/` so every import of `@abacus/ui` is unchanged (`Sheet` is an alias of `SheetModal`).
- `motion.css`: overlay keyframes and utilities (fade, scale, rise, drawer and sheet in and out); `base.css`: the CSS scroll lock for the CSP.
- `apps/web/src/app-core/overlays.ts` (the `?ov=` codec, the two-layer rule, the registry) and `overlay-host.tsx` (`useOverlays`, `OverlayHost`), mounted in `routes/root.tsx`.
- Specimens in `/components`: `o1-popover`, `c-23-drawer`, `o3-sheet-modal`, `o4-full-sheet`, `o5-command-palette`, `o6-wizard`, `c-22-dialog`, `c-22-confirm-dialog`, `o1-o6-stacking`.
- 26 conflicts between the bundles, the plan and the CSP, one line each, in `tokens/DECISIONS.md` under "Overlay stack (F-05-T20)".

**Out**
- Toasts, `ToastStore`, `useToast` (F-05-T21); the independent AC suite (F-05-T22).
- The registry entries for SHL-xx overlays: each screen epic registers its own with `registerOverlay`. The typed service API (`openSourceViewer` and the rest) is the L3 layer's.
- The Menu, Tooltip and Picker visuals (F-05-T15), beyond the stack and z-order hooks.

## Callers

No caller changed. The 13 `apps/web/src` files that import `Dialog`, `Drawer`, `Sheet`, `Popover` and `CommandPalette` compile and pass unchanged (`pnpm -C apps/web exec vitest run` 779 passed). What changes for them, without an edit: Dialog's close moves to the left of a 52 header; Drawer defaults to 440 (it was 480; `width={560}` and the older widths still work); the palette is the C-00 frame; and a controlled dialog now returns focus to the button that opened it (Radix only did that for a `Dialog.Trigger`).

## Plan

Amber zone (overlay semantics). Order: the store and its tests, `useOverlayLayer`, the frame and the layers, the layer tests, the old files removed, the codec and host with their tests, the specimens, the DECISIONS lines, the Playwright checks, the gates.

Files: as above. Registry and flag edits: none. Migrations: none. Rollback: revert the commit; the old `Dialog`, `Drawer`, `Sheet`, `Popover` and `CommandPalette` are in git history, and the exports keep their names.

Tests: `overlays/stack.test.ts` (the store), `overlays/overlays.test.tsx` (the layers), `app-core/overlays.test.ts` (the codec), `app-core/overlay-host.test.tsx` (a real router on memory history); Playwright `overlays` in `components.spec.ts` (11 layers opened live with axe on the open layer, the dirty guard, popover then dialog then drawer, never two drawers, geometry).

## Definition of done

- [x] O1 to O6 reproduce their bundles' geometry, measured in a real browser: dialog 560, drawer 440 at 10px from every edge, sheet 500 from 52 to the window's bottom, full sheet inset 14 (Playwright `geometry`); the artboards themselves show only the page under the scrim, so the layers are built from C-22, C-23, C-13 and C-00.
- [x] Escape closes only the topmost layer: popover, then dialog, then drawer, focus to each opener (unit and Playwright); a menu closes before the dialog it is in.
- [x] Two drawers never open: a second drawer or peek replaces the first in the stack (unit) and in the URL (`openRef`, `overlay-host.test.tsx`).
- [x] A peek is `role=complementary` with no scrim, no trap, no focus taken, and the page stays live.
- [x] A dirty layer asks "Discard changes?" on Escape, the close and the scrim; Keep editing is focused first; Discard closes; a replaced drawer does not ask.
- [x] Focus returns to the opener; scroll lock is released (Radix plus the CSS rule for the CSP).
- [x] `?ov=` survives a reload (the URL is drawn again), Back closes the layer, Escape and the close replace the entry, other search parameters are kept.
- [x] Reduced motion: no `motion-` class on any layer or scrim; `document.getAnimations()` stays empty on `/components`.
- [x] `pnpm -C packages/ui test`, `pnpm -C apps/web exec vitest run`, tsc and eslint for both.
- [x] `make check-fast` (see the log).

## New dependencies

None. `@radix-ui/react-dialog`, `-popover`, `-dropdown-menu` and `-tooltip` were already in `packages/ui/package.json`; there is no `@radix-ui/react-alert-dialog`, so the alertdialog is a dialog with `role="alertdialog"`.

## Progress log

- `2026-10-22` Read AGENTS.md, the amendment, F-05 section 3.E and 9, plan 04 (E3, 2.4, 5.3), the C-22, C-23, C-13 and C-00 bundles, `kits.md` "Modal Kit" and "Drawer Kit", the ENG-03 spec for the wizard, and the O1-O6 board (screenshots show the page under the scrim, not the layers).
- `2026-10-22` Built the store, the layers, the codec and host, and the specimens; tests: `packages/ui` 697 passed (about 54 new in `overlays/`), `apps/web` 779 passed (about 33 new in `app-core/`).
- `2026-10-22` Playwright against a fixtures gallery server: the 15 new `overlays` tests pass, with the existing `ac3`, `ac8`, `c-20` and inputs tests.
- `2026-10-22` Checks: `pnpm -C packages/ui test` 697 passed; `pnpm -C apps/web exec vitest run` 779 passed; tsc, eslint and prettier clean for both; `make check-fast` exit 0 (bundle budget 39 met, firm initial 228.5 of 250 KB). `make check` stage 2 not run: nothing here touches the backend.
- `2026-10-22` Gotcha: the installed Radix packages carry two copies of `react-dismissable-layer` (1.1.20 and 1.2.1), and Radix gives a keydown only to the highest layer of its own count, which also lags a layer that has just opened. A layer that cancels Escape only when it is not the stack's top left a modal that ignored Escape for a moment. Fixed by making every layer cancel Radix's Escape and close the stack's top, once (the first handler sets `defaultPrevented`).
- `2026-10-22` Gotcha: a layer under a newer modal is `aria-hidden` (Radix), so `getByRole("dialog", { name })` cannot see it, even with `hidden: true`; the tests find it by its heading.
- `2026-10-22` Gotcha: this Radix defers an outside press to the click, so a scrim press in a test is `pointerDown` with `button: 0` and then `click`.
- `2026-10-22` Gotcha: the dialog's scale-in (220ms) is mid-flight for a moment; the Playwright geometry test waits for the box to stop moving.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|
| Escape is the stack's, not Radix's | Two Radix versions count layers separately; the stack is the one order | no |
| Menus and popovers are layers of the stack | Escape order and z-order for a menu inside a dialog | no |
| Scroll lock is Radix's plus a CSS rule | `style-src 'self'` refuses Radix's injected `<style>` (R9) | no |
| `?ov=` uses the router's array form for two layers | A custom `parseSearch` would change every route | no |
| The rest are in `tokens/DECISIONS.md`, "Overlay stack (F-05-T20)" | One line each | no |

## Gotchas and discoveries

- `Dialog.Trigger` is the only thing Radix returns focus to; a controlled dialog opened from a plain button lost focus to `body`. The stack remembers the focused or pressed control now (`captureOpener`).
- Under the production CSP the scroll lock's `<style>` is refused; Radix still sets `data-scroll-locked` on the body, which the base.css rule uses.
- A held (`forceState="open"`) layer is not a layer: no scrim, no trap, no stack entry, so a page of specimens stays a page.

## Questions for the human

- [ ] Back with a dirty overlay closes it without asking (only Escape, the close and the scrim ask). A history blocker would need the router's `useBlocker` in `OverlayHost`; say if you want it before the first form-bearing overlay (SHL-14) lands.
- [ ] The plan's Drawer width of 420 to 480 and the bundle's 380, 440 and 560 disagree; the bundle won, and the default is now 440, not 480. Confirm.

## Handoff

- **Current state:** built, tested and checked; committed on this branch, not pushed.
- **Exact next step:** F-05-T21 mounts the toast host above the layers (its z is 70 in the plan; `toast.tsx` is at 60 today and was not touched); F-05-T22 writes the independent suite against `overlays/` and `app-core/overlays.ts`; screen epics call `registerOverlay` for their `?ov=` keys.
- **Known failing checks:** none.
