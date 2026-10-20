---
id: TASK-133
title: "F-05-T07 · ESLint design-system rules (palette regex that admits Accrued tokens, hex and rgba ban in packages/ui, banned utilities, toLocale and Date.now bans, brand strings) plus compiled-CSS test"
spec: SPEC-048
acceptance_criteria: [AC-5, AC-6]
risk_zone: amber
status: in-progress
epic: F-05
plan_key: F-05-T07
branch: task-133-eslint-design-rules
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan into this file before code (solo amendment: no approval step).
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Lint rejects bg-neutral-100, #7a4e12, font-semibold, text-lg, toLocaleDateString, emoji and Accrual in screens and accepts bg-green-tint and text-red-ink.

## Scope
**In**
- ESLint rules: palette regex that admits Accrued token names, hex and rgba( ban in packages/ui outside tokens/ and brand/, banned utilities (font-semibold, text-lg, shadow-lg), toLocale*/Intl/toFixed outside format.ts, Date.now() outside clock.tsx, L1 brand strings (emoji, Accrual)
- Compiled-CSS test scanning dist/*/assets/*.css for 600/700 weights outside [data-doc] and colour literals not in tokens.ts

**Out**
- Banning old Atelier classes (F-05-T34)
- The accept/reject suite itself (T08)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-5, AC-6)
- Epic: `docs/plan/epics/F-05.md`: F-05 §3 A3; F-05 §5 protected-file lines for eslint.config.js and eslint-rules.test.ts (rules extended, never weakened); F-05 §10 item 7 (compiled-CSS rules)
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T07`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [x] Plan written in this file (required for amber and red)

Steps:
1. [x] Extend eslint.config.js for apps/web and packages/ui
2. [x] Add the compiled-CSS check to stage 1
3. [x] Smoke-run against the codebase; fix or allow-list existing offenders in DECISIONS.md

Files to create or change:
- apps/web/eslint.config.js, packages/ui/eslint.config.js (extended)
- packages/ui/eslint-design-rules.js (new; the rules, shared; exported as `@abacus/ui/eslint-design-rules`)
- apps/web/scripts/check-compiled-css.js (new) and a line in `make check-fast` after `vite build`
- apps/web/src/lint/eslint-rules.test.ts (extended), apps/web/src/lint/compiled-css.test.ts (new)
- token swaps in 18 screens and 5 packages/ui components; packages/ui/src/tokens/DECISIONS.md

Tests to write (mapped to ACs):
- AC-5 -> RuleTester reject/accept cases (full coverage in T08)
- AC-6 -> compiled-CSS check fails on a seeded 700 weight and a seeded colour literal

## Definition of done
- [ ] All listed ACs have passing tests or checks that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] No secrets or real client data committed (public repo)
- [ ] No new dependencies, or each one listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation (N/A for this task unless it adds either)
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals (N/A unless it adds any)
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — task file written from the epic (SU-14); nothing built yet.
- `2026-10-20` — built with T08's tests first (about 90 new lint tests, red, then green; 137 in src/lint). Rules live in
  `packages/ui/eslint-design-rules.js`, read the colour tokens from theme.css at load, and are composed by both
  configs: palette (Tailwind families refused, token families admitted bare and with token suffixes, refused with a
  numbered shade), arbitrary colour values, hex/rgb/hsl/oklch literals (allowed in packages/ui `tokens/`, `brand/`),
  font-thin..black, default shadows, text-4xl+, `Accrual`, emoji, `toLocale*`/`toFixed`/`Intl` outside `format.ts`,
  `Date.now()` outside `clock.tsx`. Tests and *.test files are exempt, as before.
- `2026-10-20` — `text-xs..text-3xl` ban is written (`deferredTypeScaleSyntax`) but OFF: `TYPE_SCALE_BAN_ENABLED =
  false` with a TODO naming F-05-T06 (the codemod is in parallel). A test checks the flag against the shipped config and
  that the set flags text-xs..3xl when enabled. AC-5's `text-lg` rejection is therefore not live until the flag flips.
- `2026-10-20` — smoke-run found 96 violations in apps/web and 11 in packages/ui. Fixed as token swaps: `font-semibold` and
  `font-bold` to `font-medium` in 18 screens (theme.css already mapped both to 500); scrims `bg-[rgba(…)]` to
  `bg-espresso/22|12|28` and `bg-on-dark/14|22`; spinner track to `stroke-rule`. Not token swaps, so allow-listed in
  `LEGACY_FORMATTING` (30 files) and `LEGACY_CLOCK` (4 files) in apps/web/eslint.config.js until F-05-T10 builds
  format.ts and clock.tsx; recorded in packages/ui/src/tokens/DECISIONS.md.
- `2026-10-20` — compiled-CSS check (AC-6) runs after `vite build` in `make check-fast`. It compares colours by RGB (a
  minifier rewrites rgba to #rrggbbaa; opacity modifiers change alpha), allows `#0000`, and exempts Tailwind's preflight
  `optgroup { font-weight: bolder }`. Tailwind scans test files for class names, so lint tests build arbitrary-colour
  classes from parts; otherwise they compile into the production CSS and fail the check.
- `2026-10-20` — verified: `eslint .` clean in apps/web and packages/ui; `make check-fast` exit 0; `vitest run` 60 files,
  522 tests green. `make check` stage 2 (backend tests) not run: nothing in this task touches the backend.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Palette is a ban on Tailwind colour families plus the numbered shades of token families, with the token list read from theme.css | A pure allow-list cannot work (text-left, border-t, ring-2 share the prefixes); reading theme.css keeps it in step with the tokens | no |
| Type-scale ban shipped switched off | The user held it for the F-05-T06 codemod | no |
| Non-swap offenders allow-listed by file, not fixed | They need format.ts and clock.tsx (F-05-T10) | no |
| Compiled-CSS compares colours by RGB, any alpha | Opacity modifiers on tokens compile to the token colour with another alpha | no |

## Gotchas and discoveries
- Vite rewrites `new URL("./x", import.meta.url)` to an asset URL under vitest; the rules module reads theme.css with `import.meta.dirname` instead.
- A flat-config block that sets a rule replaces the earlier options, so format.ts, clock.tsx and the legacy lists each restate theirs; `"error"` alone inherits, `"off"` clears.
- `Accrual` is matched case-sensitively and whole-word; `accrual basis` stays legal.

## Questions for the human
- [ ] 

## Handoff
- **Current state:** rules, tests and the compiled-CSS check are built and green; one switch is held
- **Exact next step:** when F-05-T06 lands, set `TYPE_SCALE_BAN_ENABLED = true` in packages/ui/eslint-design-rules.js, fix what it flags, then mark done
- **Uncommitted or partial work:** none
- **Known failing checks:** none
- **Open issues:** 34 allow-listed files (format.ts, clock.tsx); Gallery.tsx is listed and another agent may be rewriting it
