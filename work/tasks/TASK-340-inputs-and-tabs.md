---
id: TASK-340
title: "F-05-T15: SearchField, FilterChip, Picker, ValueRow, Toggle, Radio, Checkbox, Fieldset, Menu, Tooltip, Segmented, SegmentedGroup, UnderlineTabs, SheetTabs, ViewToggle"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T15
branch: worktree-agent-aae32c66329c6b307
worktree: agent-aae32c66329c6b307
created: 2026-10-21
updated: 2026-10-21
---

## Plan

F-05-T15's acceptance (epic F-05 section 9, story C2): Segmented wraps with arrow keys as a tablist, no native select or boxed input exists, and every control under 24px has a 24px hit area. Builds on T14 (Button, `cn()`, the icon registry, `useReducedMotion`, `forceState`).

- **Tabs** (`components/tabs.tsx`): `nextTab()` (the bundle's roving-tabindex helper, typed), `Segmented`, `SegmentedGroup`, `UnderlineTabs`, `SheetTabs`, `ViewToggle`. One internal `Tablist`: `role=tablist` and `tab`, `aria-selected`, only the selected tab in the tab order, all four arrows move and select and wrap, disabled are skipped, Home and End jump, `onChange` once per change, an external `active` resets the selection, at most seven options a track (`devAssert`). The selected option is white and lifted and switches in place: no sliding element.
- **Inputs** (`components/inputs.tsx`): `SearchField` (28 nested pill, clear button), `Picker` (white, fill and filter variants; a pill that opens a radio menu, in place of a native select), `FilterChip` (split pill, amber when a value is chosen), `ValueRow` (C-13: select, time, text, toggle, info and paragraph rows, an invalid row says why as `role=alert`).
- **Switches and boxes** (`components/toggles.tsx`): `Toggle` (38 by 22, 34 by 20), `Checkbox` (off, on, mixed), `Radio` (17px and the 13px issue ring) and `RadioGroup` (one tab stop, arrows choose and wrap). ARIA buttons, no new dependency.
- **Fieldset** (`components/fieldset.tsx`, moved out of `overlays.tsx`): C-13 band header, `flush` rows on hairlines, `FieldsetAdd`.
- **Menu and Tooltip** (`components/popover.tsx`): Radix, upgraded to the C-00 and C-05 look. Menu items take `icon`, `checked` (a radio group: `menuitemradio`), `opensDialog` (asserted, `aria-haspopup="dialog"`), `disabled` on the trigger. Tooltip is white, with a second line, 450ms on hover and at once on focus; it needs no provider.
- **Hit areas** (`components/hit-area.ts`): `before:` pseudo-elements for the 13, 15, 17, 16, 22 and 20px controls. `hit-area.test.tsx` reads each control's size and inset from its classes and sweeps every control of the kit; a Playwright test proves a pointer 1px past the box lands on the control.
- **Specimens** (`specimens/tabs.tsx`, `inputs.tsx`, `toggles.tsx`, `menus.tsx`; 15 in the gallery): every component by variant, size and held state (hover, focus, pressed, open, disabled), the open ones drawn in place, the rest live.
- **Callers**: `Fieldset` is exported from the root as before; `Menu` keeps its `sections` API (`Workpaper.tsx` unchanged); `TooltipProvider` unchanged. No screen changed.
- No migration, no new dependency, no backend. Rollback is a revert.

## Notes

- Sources, in order: C-05 Tabs kit bundle, C-13 Edit Agent bundle (Fieldset, ValueRow, the menu), C-00 Shell Kit (menu, Go tooltip), Component Sheet family F (search, picker, filter chip, toggle, radio, checkbox), `kits.md`, the Foundations specs. Conflicts are one line each in `packages/ui/src/tokens/DECISIONS.md`, "Inputs and tabs (F-05-T15)" (28 lines).
- Component Sheet family F is "drawn inline": there is no bundle for SearchField, FilterChip or Picker, so those are built from the sheet's CSS values mapped to tokens.
- Radix's menu sets `aria-labelledby` to the trigger, which wins over `aria-label`; `Menu` clears it when the caller names the menu.

## Native selects and boxed inputs left in `apps/web/src`

Not replaced: each needs its test moved from `fireEvent.change` on a `<select>` to opening a menu, plus the jsdom shims Radix needs (`test-dom.ts`), across many files. A screen task takes its own.

- `<select>`: 47 in 24 files: Planning (4), TrialBalance (3), Fieldwork (3), Engagements (3), Completion (3), AuditLog (3), Walls (2), TieChecks (2), RollForward (2), People (2), ImportRequestList (2), FirmPeople (2), Findings (2), EngagementRecords (2), DecisionActions (2), Board (2), and one each in UnrecordedLiabilities, Overview, KnowledgeDocuments, InboxPanel, DocumentKindSelect, ClientGuidance, ClientEngagement, Autonomy. `DocumentKindSelect` is the most self-contained (one test, `spec029checks.test.tsx`).
- Boxed `Input` from `@abacus/ui` (16 files): Knowledge, FirmPeople, ReminderDrafts, EngagementRecords, KnowledgeDocuments, Engagements, Signup, DecisionActions, DueDates, Methodology, Board, MyConfirmations, AgentActivity, Budget, ItemDetail, Contacts. Plus 34 files with a raw `<input>` and 12 with a `<textarea>`.
- `Input` stays in `packages/ui/src/components/field.tsx`, marked legacy; it goes with the other Atelier exports at M3.

## Definition of done

- [x] `pnpm -C packages/ui test`: 485 tests pass (tabs, inputs, toggles, popover, hit areas).
- [x] `pnpm -C apps/web exec vitest run`: 675 tests pass, the gallery renders every specimen in jsdom.
- [x] tsc, eslint and prettier clean in `packages/ui` and `apps/web`.
- [x] Playwright `components.spec.ts` against `vite` with `VITE_UI_GALLERY=1 VITE_FIXTURES=1` (port 5234, `ABACUS_PORT_OFFSET=61`): 10 of 10 pass: axe on `/components` finds nothing serious, `getAnimations()` is empty under reduced motion, hit areas land in a real browser, Segmented wraps, ViewToggle opens and Escape returns focus, a tooltip opens on keyboard focus.
- [x] Looked at the Segmented, ViewToggle, value-row, fieldset and menu specimens against the C-05 and C-13 screenshots in the browser.
- [ ] Parity Tier A baselines: not captured here (the harness is F-05-T16).
- [x] `make check-fast` passes (backend gates, tsc, eslint, prettier, `vite build`, compiled-CSS check). `make check` stage 2 (backend tests) is not run: no backend file changed.

## Progress log

- `2026-10-21` Built the kit, 15 specimens, five test files and four Playwright tests; logged the conflicts.
- `2026-10-21` Gotcha: Radix moves focus on the next tick (`setTimeout`) after an arrow key and on close, so a unit test waits (`waitFor`) rather than reading `document.activeElement` at once.
- `2026-10-21` Gotcha: Radix needs `ResizeObserver` and pointer-capture methods that jsdom lacks; `test-dom.ts` installs them for the tests that open a real menu. A held (`forceState="open"`) menu is drawn in place, so the gallery test in `apps/web` needs none.
- `2026-10-21` Gotcha: axe flagged the `ink-4` text of a disabled radio option, because the label is not a disabled control; `aria-disabled` on the text span exempts it.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
| --- | --- | --- |
| Tabs hold their selection and reset on an external `active`, as C-05 says | The bundle's behaviour; a parent that follows `onChange` is controlled in effect | no |
| Held `open` menus and tooltips are drawn in place, not in a layer | One page of specimens; no layout needed in jsdom | no |
| `Input` stays, marked legacy; no screen is converted here | 47 selects and 50 inputs need their tests moved; screens own that | no |

## Handoff

Done. F-05-T18 (Toolbar, Tabsbar, RecordHeader) mounts `Segmented`, `ViewToggle` and the Picker; place `ViewToggle` at right 12 there, the kit does not position itself. F-05-T20 owns the layer stack: `Menu` and `Tooltip` use `z-50` and `z-[70]` until then. Screen tasks replace `<select>` with `Picker` and `Input` with `ValueRow` or `SearchField`.
