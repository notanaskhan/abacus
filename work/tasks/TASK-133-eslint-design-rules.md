---
id: TASK-133
title: "F-05-T07 · ESLint design-system rules (palette regex that admits Accrued tokens, hex and rgba ban in packages/ui, banned utilities, toLocale and Date.now bans, brand strings) plus compiled-CSS test"
spec: SPEC-048
acceptance_criteria: [AC-5, AC-6]
risk_zone: amber
status: todo
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
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Extend eslint.config.js for apps/web and packages/ui
2. [ ] Add the compiled-CSS check to stage 1
3. [ ] Smoke-run against the codebase; fix or allow-list existing offenders in DECISIONS.md

Files to create or change:
- apps/web/eslint.config.js
- packages/ui/eslint.config.js
- apps/web/src/lint/eslint-rules.test.ts
- the compiled-CSS check script

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
