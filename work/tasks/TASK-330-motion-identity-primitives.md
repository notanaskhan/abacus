---
id: TASK-330
title: "F-05-T14 (motion and identity half): Spinner, Pulse, Reveal, TypingDots, useReducedMotion, Person, Monogram, AgentAvatar, FirmMark, Wordmark"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T14
branch: worktree-agent-abf03ad584c1d7d49
worktree: agent-abf03ad584c1d7d49
created: 2026-10-21
updated: 2026-10-21
---

## Plan

F-05-T14 is split between two builders. This half is motion and identity; the other half (TASK-329) is Button, IconButton, Pill, Count, Tag, DoneCount and CheckPill, and owns `button.tsx`, `cn.ts` and the radius tokens. Acceptance: every variant, size and forced state renders as a specimen in `/components`, and reduced motion leaves `document.getAnimations()` empty.

- **Hook** (`packages/ui/src/motion.ts`): `useReducedMotion()` over `matchMedia("(prefers-reduced-motion: reduce)")` with `useSyncExternalStore`; `useMotion(still)` for components; `useWordReveal(text)` for the 20ms-a-word reveal. The plan names no app-level override, so there is none.
- **Components** (`components/motion.tsx`): `Spinner`, `Pulse`, `LiveDot`, `Reveal`, `TypingDots`. Under the preference each renders no `motion-*` class, no animation delay and no timer. `still` forces that form. `surfaces.tsx` re-exports `Spinner`, so the existing call sites are unchanged.
- **Identity** (`packages/ui/src/brand/`, as the plan's tree names it): `Wordmark`, `Monogram`, `AgentAvatar`, `FirmMark`, `Person`, `PersonAvatar`, `PersonStack`. Monogram, AgentAvatar and the tile in FirmMark reuse the registry's `AgentMonogram`; `icons.tsx` is untouched.
- **motion.css**: `ac-pulse` and `ac-typing` corrected to the bundle, `ac-breathe` and `motion-breathe` added, and the reduced-motion block also clears animation delays.
- **Specimens**: eight in the gallery (C-20 spinners and pulse, C-10 reveal and typing dots, FND-01 wordmark and monogram, C-00 firm mark, C-28 people), each size, tint and form, the running form beside the still one.
- **Tests**: `motion.test.tsx` (hook, no animation class or delay under the preference, word reveal on fake timers, motion.css values) and `brand/brand.test.tsx`; Playwright in `apps/web/e2e/components.spec.ts`.
- No migration, no new dependency, no backend change. Rollback is a revert.

## Notes

- Sources, in order: Foundations 01 Brand with its README and IMPLEMENTATION; C-20, C-26, C-28 and C-10 bundles; `kits.md`. Conflicts are one line each in `packages/ui/src/tokens/DECISIONS.md`, "T0 motion and identity (F-05-T14)".
- The Agent is never shown as a person: `AgentAvatar` takes no name, draws no initials and has `data-actor="agent"`. The chat kit draws no avatars in the thread, and neither does this task.
- The firm app's chrome carries no Accrued logo (brand spec). Nothing here places `Wordmark` or `Monogram` in the shell; the guard for it is the placement rule in their doc comments and the screen reviews.
- Class merging uses `clsx`, as in the status kit.

## Definition of done

- [x] `pnpm -C packages/ui test`: 277 tests pass (hook, animation-free rendering under the preference, word reveal, brand, initials).
- [x] `pnpm -C apps/web exec vitest run`: 669 tests pass.
- [x] tsc and lint clean in `packages/ui` and `apps/web` (after `pnpm -C packages/api-client build:types`).
- [x] Playwright `components.spec.ts` against `vite` with `VITE_UI_GALLERY=1 VITE_FIXTURES=1` on port 5230: 6 of 6 pass, including axe on `/components` (the new specimens) and `getAnimations()` empty with `reducedMotion: "reduce"`; with motion allowed the same page runs `ac-spin`, `ac-pulse`, `ac-breathe` and `ac-typing`, so the check is not vacuous.
- [x] Checked the wordmark, monogram and stack against the Foundations 01 and C-28 screenshots in the browser.
- [ ] Parity Tier A baselines: not captured here (the harness is F-05-T16); spinners and presence avatars are masked there anyway.

## Progress log

- `2026-10-21` Built the hook, five motion components, five identity components, eight specimens and tests; fixed `ac-pulse`, `ac-typing` and the reduced-motion backstop in motion.css.
- `2026-10-21` Gotcha: a word-reveal chain of `setTimeout`s advances one word per render, so a test must step 20ms at a time, not 60ms at once.
- `2026-10-21` Gotcha: `toLocaleUpperCase` is refused outside format.ts by lint; initials use `toUpperCase`.

## Decisions made during this task

| Decision                                                       | Reason                                                 | Needs ADR? |
| -------------------------------------------------------------- | ------------------------------------------------------ | ---------- |
| Reduced motion draws a still spinner, not a slow one           | The plan's acceptance is an empty `getAnimations()`    | no         |
| Idle avatar fades the fill, not the initials                   | DEC-11; faded initials fail AA                         | no         |
| Minimum monogram size is a type and a clamp, not a dev warning | The ui package has no env access and lint bans console | no         |

## Gotchas and discoveries

- The Presence stack's overlap hides most of a covered avatar's initials; the handoff screenshot shows the same ("H(SB"), so it is not a bug.
- Port 5199 was held by another session's dev server; the gallery check used 5230 with `ABACUS_PORT_OFFSET=57`.

## Handoff

Done. Merge order with TASK-329: both edit `specimens/index.ts` and `index.ts`, so expect two trivial conflicts there. `specimens/frame.tsx` repeats the status specimens' `Sheet` and `Row` and can replace them. F-05-T15 builds on Button; F-05-T19 rebuilds `Skeleton` on `Pulse`; F-05-T30 builds `HumanAction` and `formatActor` next to `AgentAvatar`.
