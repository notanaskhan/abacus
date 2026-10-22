---
id: TASK-387
title: Retire the Atelier tokens and fonts (F-05-T34, DS-32)
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: F-05
plan_key: F-05-T34
branch: f05-t34-retire-atelier
created: 2026-10-22
updated: 2026-10-22
---

## Objective
F-05 J3 and definition-of-done item 8: once the theme swap is complete, Source Sans 3 and
Newsreader leave `package.json` and the dependency allowlist, and lint bans `bg-ground`,
`text-muted`, `border-line`, `bg-accent`, `text-info` and `text-ai`. Acceptance: no such class
remains and both font packages are gone.

## Plan (red zone)
- Files: every `apps/web/src/legacy/*` and `apps/web/src/shell/*` file using an Atelier token;
  `packages/ui/src/theme.css`, `contrast.css`, `tokens/tokens.ts` (mirror), `eslint-design-rules.js`,
  `components/workspace.tsx`, `index.ts`, `packages/ui/package.json`, `pnpm-lock.yaml`,
  `docs/architecture/dependency-allowlist.yaml`, `apps/web/src/lint/eslint-rules.test.ts`.
- No migrations, registry or flag edits.
- Tests: new `F-05 J3` cases in `eslint-rules.test.ts`; `tokens-mirror.test.ts` keeps proving
  theme.css equals tokens.ts.
- Rollback: revert the one commit; the aliases and font packages come back with it.

## What changed
- Codemod (exact value matches, so nothing moves visually): `ground` → `shell`, `muted` → `ink-3`,
  `line` → `hair`, `accent` → `espresso`, `accent-hover` → `cta-hover`, `accent-soft` → `sel-bg`,
  `on-accent` → `on-dark`, `info` → `amber-ink`, `info-soft` → `amber-tint`, `ai-line` → `stroke`
  (`ai` → `ink-3` in the ban message; no `text-ai` use remained). Applied under every colour prefix
  and variant: 211 `text-muted`, 65 `border-line`, 25 `text-accent`, 7 `divide-line`, 6 `bg-ground`,
  6 `bg-accent`, 4 `border-ai-line`, 2 `bg-accent-soft`, 2 `text-info`, 2 `text-on-accent`,
  1 each of `outline-accent`, `border-t-accent`, `bg-line`, across 55 files.
- `theme.css`, `tokens.ts`: the eleven Atelier colour variables are gone; the SPEC-016 aliases
  still in use (`surface`, `rail`, `sunken`, `ok`, `warn`, `danger` and their `-soft`) stay until
  their screens are replaced. `contrast.css` and `referenceLadder` drop `--color-muted` (the
  reference ladder already overrides `--color-ink-3`, which now carries those uses).
- `eslint-design-rules.js`: `RETIRED_TOKENS` and `RETIRED_TOKEN_SOURCE`, a `designSyntax` entry
  that refuses a utility on any retired token under any colour prefix and variant, in apps/web and
  packages/ui. The palette message now names `bg-card` and `text-ink-3`.
- `eslint-rules.test.ts`: the SPEC-016 "ac1 allows the tokens" case uses the live names
  (`bg-surface text-ink-3 border-hair`; the intent, tokens pass, is unchanged); new cases prove
  each retired class is refused in apps/web and packages/ui and the replacements and look-alikes
  (`border-amber-line`, `whitespace-pre-line`) are not.
- `@fontsource/source-sans-3` and `@fontsource/newsreader` removed from `packages/ui/package.json`,
  the lockfile and the allowlist (nothing imported them).
- `Rail` and `RailButton` (unused) deleted from `packages/ui` (DoD item 8). `ClientBell` stays with
  its test until P-08.

## Definition of done
- [x] No retired class left in `apps/web/src` or `packages/ui/src`
- [x] ESLint clean in apps/web and packages/ui; `eslint-rules.test.ts` and `tokens-mirror.test.ts` pass
- [x] `tsc --noEmit` clean for packages/ui; apps/web clean apart from the existing generated
      api-client errors; `vite build` succeeds

## Progress log
- 2026-10-22: done in one session (S3 batch: static checks and the two lint test files only; the
  full suites run in CI on the batch).
