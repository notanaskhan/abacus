---
id: TASK-132
title: "F-05-T06 · Codemod DS-06 before the theme swap: bg-surface to bg-card first, spacing x4, text-sm/xs to text-body/meta, font-semibold to font-medium, borders to shadow-e1"
spec: SPEC-048
acceptance_criteria: [AC-9]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T06
branch: task-132-codemod-leftover-check
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
The codemod lands before the theme swap and all 291 Vitest cases plus e2e/journey.spec.ts stay green with no test weakened.

## Notes
Decided 2026-10-20: this task runs only as a check for leftover classes, because the theme swap is done. The CSV acceptance text below describes the original codemod; the check-only scope is what to build.

## Scope
**In**
- Run the DS-06 rewrite rules (bg-surface to bg-card, spacing x4, text-sm/xs to text-body/meta, font-semibold to font-medium, borders to shadow-e1) in report-only mode over apps/web/src
- Record leftovers and fix any found
- Keep all 291 Vitest cases and e2e/journey.spec.ts green

**Out**
- Performing the theme swap (already done)
- Moving screens into legacy/ (F-05-T23)
- Editing tests to pass (never)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-9)
- Epic: `docs/plan/epics/F-05.md`: F-05 §3 J1 and J3; F-05 §10 item 8; F-05 §11 R7 (the 291 Vitest cases; three tests assert visible 'AI' text)
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T06`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Write the check script from the rule list
2. [ ] Run it; list leftover classes
3. [ ] Fix or add to DECISIONS.md; re-run Vitest and journey e2e

Files to create or change:
- apps/web/scripts/ds-leftover-check (or the repo's scripts dir)
- apps/web/src/** (only the leftovers found)

Tests to write (mapped to ACs):
- AC-9 -> check output empty; Vitest 291 cases and e2e/journey.spec.ts pass unchanged

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
- 2026-10-20 (SU-24): default palette and shadows are already reset (no uses left). Tailwind's text-* sizes are still used 318 times in 56 files, mapped onto the plan's roles; the codemod replaces them with role utilities before the --text-* reset.

- 2026-10-20 (F-05-T06 built): codemod at `apps/web/scripts/ds06-codemod.ts` (rules in `apps/web/src/lint/ds06-codemod.ts`, tests in `ds06-codemod.test.ts`). Run over `apps/web/src` and `packages/ui/src`: 325 uses in 58 files (the 318/56 above was an earlier count). Mapping: xs to meta, sm to body, base to nav, lg to pane, xl to title, 2xl and 3xl to dashboard; the roles are copied from the fonts/tokens branch (b6a131a). `--text-*: initial` is now in theme.css; `tokens.test.ts` asserts text-xs..3xl compile to nothing and the roles compile; a test compares every role's size and line height with the old mapping. Second run reports 0 files. Vitest 429 passed, `vite build` clean.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| text-base maps to text-nav, not text-tab | tab is 14px in the shared roles; nav is 13.5/1.45, an exact match | no |
| Roles keep today's line heights, with no weight or tracking | no screen may change size; body 1.2 is F-05-T05's open decision | no |
| A file may opt out with the line `ds06-codemod: keep` | the codemod test and token test name old classes as probes | no |

## Gotchas and discoveries
- 

## Questions for the human
- [ ] 

## Handoff
- **Current state:** done; codemod run, reset in place
- **Exact next step:** none (F-05-T23 and T34 follow)
- **Uncommitted or partial work:** none
- **Known failing checks:** none
- **Open issues:** none
