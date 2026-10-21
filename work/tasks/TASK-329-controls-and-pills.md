---
id: TASK-329
title: "F-05-T14 (controls half): Button, IconButton, Pill, Count, Tag, DoneCount, CheckPill, the cn() type-role fix, and the TASK-093 squares reverted to pills"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-14]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T14
branch: worktree-agent-a519081bdd8c5f005
worktree: agent-a519081bdd8c5f005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
F-05-T14's acceptance (epic F-05 section 9): every variant, size and forceState renders as a specimen at parity Tier A, and reduced motion leaves `document.getAnimations()` empty. This task is the controls half; the motion and identity half (Spinner, Pulse, Reveal, TypingDots, useReducedMotion, Person, Monogram, AgentAvatar, FirmMark, Wordmark) is built in parallel by another session (TASK-330 or later) and is not touched here. Tick came from F-05-T12 and is reused.

- **cn()** (`packages/ui/src/cn.ts`): `extendTailwindMerge` registers the roles of `tokens.ts` `textRoles` as font sizes, so `cn("text-meta", "text-ink-2")` keeps both. `cn.test.ts` proves it for every role in theme.css.
- **Pill** (`components/pill.tsx`): the shared base (variants, sizes, the ring, the check and chevron), plus Count (`default`, `bad`, `segment`), Tag, DoneCount (complete, partial, none) and CheckPill (approved with a count, unapproved). `StatusPill` is now `Pill` plus the earlier `tone` prop and the sync chip's glyph (as `lead`); Tick and SyncChip build on the same classes. The status kit joins classes with `cn` again.
- **Button and IconButton** (`components/button.tsx`): pills (DEC-124), the plan's seven variants (`primary`, `secondary`, `tonal`, `ghost`, `destructive`, `success`, `link`) and six sizes (`xs` 23 to `xl` 36); IconButton is `white` 28, `fill` 30, `dark` 29. Props: `icon`, `iconAfter`, `loading`, `opensDialog`, `forceState`, `asChild` (Button). `opensDialog` asserts a trailing U+2026 in development and in tests (`dev.ts`) and sets `aria-haspopup="dialog"`.
- **forceState** (`force-state.ts`): `data-force="hover|focus|pressed|loading"`; `base.css` draws `[data-force="focus"]` as the global outline; `utilities.css` gains `press` and `pressed` (180ms colour, 220ms press, scale .985 and brightness .97).
- **Squares reverted** (DEC-124): `button.tsx`, the dialog and drawer close buttons, Badge, the AiTag chip, RailButton, and the TASK-093 sites in the app shell (Layout, Tabs, EngagementLayout, Palette, Board, Engagements, CommentThread, InboxPanel) are `rounded-pill`. `--radius-control` and `--radius-panel` stay: about 60 selects, textareas and panels read them.
- **Specimens** (`specimens/controls.tsx`, seven in the gallery): Button (variant by state, size, icon, ellipsis, link), IconButton, Pill (every variant by every size), Count, Tag, DoneCount, CheckPill.
- **Callers**: `variant="outline"` to `secondary`, `"danger"` to `destructive`, `"default"` to `primary` (about 90 sites in 44 files, by sed and tsc); `Count` (done / total) in Overview.tsx is `Fraction`.
- No migration, no new dependency, no backend. Rollback is a revert.

## Notes
- Conflicts between the bundles, the Component Sheet, `kits.md`, the plan and the repo are one line each in `packages/ui/src/tokens/DECISIONS.md`, "Buttons and pills".
- The bundle and the sheet disagree on the secondary and icon hover (nested against nav-fill); C-00 wins, as the bundles outrank the sheet.
- `pnpm install` was needed in the worktree before any check would run (no `node_modules` came with it).

## Definition of done
- [x] `cn.test.ts` (6), `button.test.tsx` (every variant, size, forced state, loading, the ellipsis rule, hit area) and `pill.test.tsx` (every variant and size, the marks, StatusPill and Tick on Pill); `packages/ui` 323 tests.
- [x] `apps/web` tests (667) pass, including `status/statusKit.test.tsx` unchanged.
- [x] tsc and eslint pass for `packages/ui` and `apps/web`; prettier is clean.
- [x] The gallery checked in the browser against the Component Sheet (E) and C-06 screenshot 03; axe finds nothing serious or critical on `/components` (two moderate landmark findings from the index page predate this task).
- [x] With `prefers-reduced-motion: reduce` the gallery holds 36 rings and `document.getAnimations()` is empty.

## Progress log
- `2026-10-21` Built the pill family, Button and IconButton, the specimens and the tests; moved the callers; reverted the squares.
- `2026-10-21` Gotcha: `base.css` and `contrast.css` are parsed by `lint/base-css.test.ts` and `lint/tokens.test.ts` with a regex that expects `:focus-visible { ... }` alone. A grouped selector (`:focus-visible, [data-force="focus"]`) broke both, so the forced focus is its own rule.
- `2026-10-21` Gotcha: an SVG's `className` is an `SVGAnimatedString`, so a test helper that splits it must read the `class` attribute.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Button names and sizes from the plan (04 section 6, DS-15), callers moved | One vocabulary with the kit | no |
| `opensDialog` asserts, it does not append | Plan 04 rule 9 and L3 say asserted; the copy registry owns the words | no |
| StatusPill refactored onto Pill | Clean: the status kit's 62 tests pass unchanged | no |
| TASK-093 squares reverted in the app shell too | DEC-124 reverts them; leaving them would mix shapes on one toolbar | no |
| `--radius-control` and `--radius-panel` kept | About 60 non-button call sites | no |

## Gotchas and discoveries
- Tailwind sees class names in the source text, so a class built at run time (`"hover:" + name`) is never generated; the Button maps write every `hover:` and `data-[force=...]:` class out.
- `px-[Npx]` with a later `pl-[Mpx]` is order-dependent in the generated CSS, so the size table keeps three whole padding strings per size (plain, with an icon, with the ring) instead of overriding.

## Handoff
Done. The other F-05-T14 half merges into the same `index.ts` and `specimens/index.ts`; both lists are alphabetical-by-kit, so a clean merge is a union. `Ring` (components/pill.tsx) is the pill's and the button's spinner; the Spinner of the motion half may take it or replace it. F-05-T15 moves the remaining `--radius-control` and `--radius-panel` sites.
