---
id: TASK-005
title: "Kernel: config, logging, tenant sessions with row-level security, migrations"
spec: SPEC-000
acceptance_criteria: [AC-5, AC-13, AC-20]
risk_zone: red
status: todo
branch:
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Shared kernel foundations every module depends on: settings, classification-aware structured logging, the application and migration database roles, `tenant_session(ctx)` with row-level security, Alembic, and the real `schema_check` (replacing TASK-002's guard).

## Scope
Defined when the plan is written. Starts after TASK-004.

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-014, ADR-015, ADR-022, ADR-031, ADR-091, ADR-101

## Plan
- [ ] Plan approved by human (required for amber and red)
- Red task: the agent drafts the design here; the founder edits or approves it before any code, then reviews the diff line by line (founder decision 2026-10-06).

Steps: to be written when the task starts.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder. Not started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
-

## Handoff
- **Current state:** Not started.
- **Exact next step:** Write the plan once TASK-004 is done.
