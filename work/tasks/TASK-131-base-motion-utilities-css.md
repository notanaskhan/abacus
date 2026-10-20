---
id: TASK-131
title: "F-05-T05 · base.css, motion.css, utilities.css (hairline, pane, well, tabular, doc-scope) with reduced-motion and forced-colors blocks"
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: todo
epic: F-05
plan_key: F-05-T05
branch: task-131-base-motion-utilities-css
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
body computes to 13px/15.6px Geist with tabular numbers on #F8F8F6 and forced-colors keeps pane edges and the .55 focus outline.

## Scope
**In**
- base.css, motion.css, utilities.css (hairline, pane, well, tabular, doc-scope)
- reduced-motion and forced-colors blocks

**Out**
- Component use of the utilities
- Parity harness (T16)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-8)
- Epic: `docs/plan/epics/F-05.md`: F-05 §3 A2 (focus outline) and the tokens it uses; F-05 §5 L0 row and Tier D computed-style line (body 13/15.6 Geist, pane radius 12, gutter 10); F-05 §3 I2 for the Tier D reference
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T05`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Write the three files over the T03 tokens
2. [ ] Add @media (prefers-reduced-motion) and (forced-colors: active) blocks
3. [ ] Computed-style test in the gallery/e2e

Files to create or change:
- packages/ui/src/base.css
- packages/ui/src/motion.css
- packages/ui/src/utilities.css

Tests to write (mapped to ACs):
- AC-8 -> body computes 13px/15.6px Geist, tabular numbers, #F8F8F6; forced-colors emulation keeps pane edges and the .55 focus outline

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
- 2026-10-20 (SU-24): open for the builder: the plan's body line height is 15.6px (1.2); the app ships 13px/1.45. Changing it moves every screen; decide here and record in tokens/DECISIONS.md.

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
