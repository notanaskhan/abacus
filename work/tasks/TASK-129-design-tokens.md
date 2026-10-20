---
id: TASK-129
title: "F-05-T03 · Tokens: tokens.ts, theme.css (@theme static with namespace resets), root.css, contrast.css (AA ladder plus reference mode)"
spec: SPEC-048
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-14]
risk_zone: green
status: in-progress
epic: F-05
plan_key: F-05-T03
branch: task-129-design-tokens
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
tokens.test.ts proves exact equality with tokens.ts and a probe using bg-red-500 text-sm shadow-lg compiles to no CSS rules.

## Notes
Decided 2026-10-20: controls use pills (`--radius-pill`); Anas's 7px squared controls revert in F-05-T14, not here.

## Scope
**In**
- tokens/tokens.ts listing every foundations value (9 surfaces, 7 inks, 5 dark fills, 3 status families with hovers, clay, 8 match, 8 viz, 10 doc, 22 type roles, 13 radii incl. --radius-pill, 14 shadows, 3 scrims, motion, z-index, about 25 layout sizes)
- theme.css as @theme static with namespace resets; root.css; contrast.css with the AA ladder and data-contrast=reference
- tokens.test.ts equality test and the probe compile test

**Out**
- Fonts (T04), base/motion/utilities CSS (T05), lint (T07), gallery (T09)
- Changing primitives to use pills (F-05-T14)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-1, AC-2, AC-3, AC-4, AC-14)
- Epic: `docs/plan/epics/F-05.md`: F-05 §3 A1 and A2; F-05 §5 L0 row (tokens.ts, theme.css with --spacing 1px and breakpoints 390/768/1100/1280/1440, root.css, contrast.css, DECISIONS.md); F-05 §10 items 3 and 4; F-05 §11 R3, R8
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T03`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Diff existing theme.css against design-foundations; write tokens.ts as the single source
2. [ ] Reset Tailwind namespaces with `initial`; keep legacy classes the codebase still uses until T34
3. [ ] Add contrast.css and the reference-mode attribute
4. [ ] Write tokens.test.ts and the probe file test; run Vitest

Files to create or change:
- packages/ui/src/tokens/tokens.ts
- packages/ui/src/tokens/tokens.test.ts
- packages/ui/src/theme.css
- packages/ui/src/root.css
- packages/ui/src/contrast.css

Tests to write (mapped to ACs):
- AC-1 -> tokens.test.ts equality
- AC-2 -> probe compiles to no rules; token utilities emit exact values
- AC-3 -> axe on /components/** (wired in T09)
- AC-4 -> data-contrast=reference restores handoff ladder
- AC-14 -> --radius-pill in tokens.ts and theme.css

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
- 2026-10-20 (SU-24): tests first in apps/web/src/lint/tokens.test.ts, then fixed: ink-2 .70 and ink-3 .66 (AA on every surface), match text #7E4590, focus outline 2px rgba(43,31,23,.55), Tailwind's default palette and shadows reset; ClientBell shadow-lg -> shadow-pop. Still to do here: the typed tokens.ts mirror and root.css.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- 

## Questions for the human
- [ ] 

## Handoff
- **Current state:** not started
- **Exact next step:** step 1 of the plan
- **Uncommitted or partial work:** none
- **Known failing checks:** none
- **Open issues:** none
