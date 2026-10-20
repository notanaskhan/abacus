---
id: TASK-134
title: "F-05-T08 · Independent AC tests for the font and lint tasks (ADR-078)"
spec: SPEC-048
acceptance_criteria: [AC-5, AC-7]
risk_zone: amber
status: todo
epic: F-05
plan_key: F-05-T08
branch: task-134-independent-ac-tests
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
A separate session's tests cover every accept and reject case of the lint AC and the font request log without weakening eslint-rules.test.ts.

## Scope
**In**
- Tests covering every accept and reject case of the lint AC (AC-5)
- Playwright font request-log test (AC-7)
- No weakening of eslint-rules.test.ts

**Out**
- Writing the rules or fonts themselves (T04, T07)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-5, AC-7)
- Epic: `docs/plan/epics/F-05.md`: F-05 §3 A3 and A4; F-05 §9 (ADR-078 independent AC test rows) and §10 item 11; F-05 §5 protected-file line for eslint-rules.test.ts
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T08`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Under the solo amendment ADR-078's separate author is void: write these tests from SPEC-048 first, then confirm T04 and T07 pass them, without editing the tests to fit
2. [ ] List each accept and reject string from AC-5 as a case
3. [ ] Add the font request-log test (ds-fonts.spec.ts)

Files to create or change:
- apps/web/src/lint/eslint-rules.test.ts (extend only)
- apps/web/e2e/ds-fonts.spec.ts

Tests to write (mapped to ACs):
- AC-5 -> one case per string in the AC
- AC-7 -> request log contains no fonts.googleapis.com or fonts.gstatic.com; CSP meta unchanged

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
