---
id: TASK-008
title: Engagements and request items through the API
spec: SPEC-000
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: amber
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
Engagement and request-item modules with routes, services and repositories; OpenAPI export and the generated TypeScript client (switches on the api-client drift check).

## Scope
Defined when the plan is written. Starts after TASK-007.

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md`
- ADRs: ADR-008, ADR-012, ADR-013

## Plan
- [ ] Plan approved by human (required for amber and red)


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
- **Exact next step:** Write the plan once TASK-007 is done.
