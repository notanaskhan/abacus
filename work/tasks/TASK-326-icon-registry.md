---
id: TASK-326
title: "F-05-T13: the icon registry, handoff names to lucide-react 1.52.0, custom glyphs and the /components/icons gallery"
spec: SPEC-048
acceptance_criteria: [AC-3, AC-10]
risk_zone: green
status: done
branch: worktree-agent-a6fde5c36bd0f9ad7
worktree: agent-a6fde5c36bd0f9ad7
created: 2026-10-21
updated: 2026-10-21
---

## Objective
One icon registry: every lucide name the handoff uses resolves on `lucide-react@1.52.0` (DF-37), a lucide upgrade cannot silently blank a glyph, and the marks the handoff draws itself are custom SVG glyphs.

## Scope
**In**
- `packages/ui/src/icons/`: `names.ts` (the typed `IconName` union), `registry.ts` (kebab name to named-import component, plus `ICON_SUBSTITUTES`), `icon.tsx` (`Icon`: size 12 to 22, 1.5 stroke in viewBox units, `aria-hidden` unless `label`), `custom.tsx` (Agent monogram, atom mark, half disc, vendor monogram tile).
- `packages/ui/src/icons.test.ts` and the `test` script, `vitest` and `react-dom` as devDependencies of `packages/ui` (both already allowlisted).
- `/components/icons` in the gallery, its nav link, a route test and the axe pass in `e2e/components.spec.ts`.
- `ci-frontend` also runs the `packages/ui` tests.

**Out**
- Button and control shape (F-05-T14). The `Monogram`, `AgentAvatar`, `Wordmark` primitives stay with T14; this task draws the glyphs only.
- Parity masks for the blank icons (F-05-T16).

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md`; epic `docs/plan/epics/F-05.md` §3.B (B3), §5 route table.
- Decisions: DF-37 in `docs/plan/09-decisions-adrs.md`.
- Handoff: `handoff/design-tokens.md` (Icons), `accrued-ui.js` (`lc-i`, `ac-disc`), `_foundations/.../specs/01-brand.md`, C-11, C-14, C-26, C-33, C-34 kit specs.

## Plan
Steps:
1. [x] Count the names: the 212 in `accrued-ui.js`, the 22 in design-tokens.md, and any the handoff uses that neither lists.
2. [x] Map each to a lucide-react 1.52.0 export, by named import; record every name lucide renamed since 0.469, and the DF-37 substitute.
3. [x] Write `icons.test.ts` (resolve, stroke in viewBox units at 12 to 22, no colour literals), then the registry, `Icon` and the glyphs.
4. [x] Gallery page and route test.

Files to create or change:
- `packages/ui/src/icons/{names,registry,icon,custom,index}.ts[x]`, `packages/ui/src/icons.test.ts`, `packages/ui/src/node-shim.d.ts`, `packages/ui/src/index.ts`, `packages/ui/package.json`, `pnpm-lock.yaml`.
- `apps/web/src/gallery/pages.tsx`, `apps/web/src/gallery/routes.test.tsx`, `apps/web/src/router.tsx`, `apps/web/e2e/components.spec.ts`, `Makefile`.

Tests to write (mapped to ACs):
- AC-3 (B3) -> `icons.test.ts`: counts, every name resolves, strokes, custom glyphs without brand colours.
- AC-10 -> `gallery/routes.test.tsx` "F-05-T13 icons page".

## Definition of done
- [x] `pnpm -C packages/ui test` (17) and `pnpm -C apps/web test` (606) pass.
- [x] Lint, prettier and `tsc` pass for `packages/ui`; lint and prettier pass for `apps/web`.
- [x] Production build has no gallery strings (`dist.test.ts`); compiled-CSS check clean with and without the gallery.
- [x] No new dependency (vitest and react-dom are allowlisted; `packages/ui` gains them as devDependencies only).

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| vitest (dev, `packages/ui`) | ^5.0.3 | `icons.test.ts` | allowlisted |
| react-dom (dev, `packages/ui`) | ^19.3.0 | `renderToStaticMarkup` in the test | allowlisted |

## Progress log
- `2026-10-21` - Counted the names, built the registry, `Icon`, the four custom glyphs, the gallery page and tests. Ui tests 17, web tests 606.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The registry holds 252 names, not 234: the 212 and 22 plus 18 more | The handoff's table lists only names written as `<lc-i n="...">`. Kit data and dynamic bindings use 18 more that are in neither list (`activity`, `book-open-check`, `calendar-x`, `car`, `dollar-sign`, `factory`, `file-type`, `file-x`, `hard-hat`, `heart-handshake`, `indent`, `lock-open`, `shield`, `sticky-note`, `stethoscope`, `store`, `truck`, `wheat`). They render blank in the PNGs like the 22 | no |
| No name is missing from lucide-react 1.52.0; the substitutes are renames | Every one of the 252 resolves. 15 names are deprecated aliases in 1.52.0 (`trash-2` is `trash`, `align-left` is `text-align-start`, `filter` is `funnel` ...): the registry imports the current name, same glyph, and lists it in `ICON_SUBSTITUTES` | no |
| `gantt-chart` is `chart-gantt` (DF-37) | DF-37 names it. Lucide's own alias for it is `chart-no-axes-gantt` (no axes); PF can switch the one entry if the axes show in the Plan kit | no |
| Custom glyphs use `currentColor` or a token class | "No brand colours": the monogram tile is `fill-espresso` with the `fill-green` posted dot, vendor tiles take a C-14 category tone and initials, never a vendor colour | no |
| `Icon` sizes are 12 to 22 | The task's range. The handoff's 10 to 11 px checks live inside pills and discs, which draw their own glyphs | no |

## Gotchas and discoveries
- Lucide 1.52.0 `absoluteStrokeWidth` is deprecated; the default (off) is what scales the stroke with the box, so `Icon` passes neither.
- The handoff's `home`, `gift`, `mic`, `vote` and `target` in kit data are file-kind keys, not icon names; they are not registered.
- `packages/ui` has no `@types/node`; `src/node-shim.d.ts` types the three Node modules the test reads.

## Questions for the human
- [ ] Is `chart-gantt` (axes) or `chart-no-axes-gantt` right for IAU01 "Open timeline"?

## Handoff
- **Current state:** done; committed on this branch.
- **Exact next step:** F-05-T14 builds `Monogram`, `AgentAvatar` and `Wordmark` on `AgentMonogram` and the tokens; F-05-T16 masks the blank icon positions.
- **Known failing checks:** `tsc` in `apps/web` reports errors inside generated `packages/api-client/src` only; none from this task.
