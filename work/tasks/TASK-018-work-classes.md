---
id: TASK-018
title: Work-class queues and admission control
spec: SPEC-003
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16]
risk_zone: amber
status: todo
branch:
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-003. All asynchronous work runs on four work-class task queues with their own worker pools, behind one `dispatch`, with per-firm and per-engagement caps (ADR-071). Every model call is admitted through the gateway against shared provider capacity, by priority, degrading visibly (ADR-072).

## Scope
All of SPEC-003 (AC-1 to AC-16), once approved. Excluded: the budget hierarchy and metering (ADR-069), the second model route (ADR-073), autoscaling, and Terraform (TASK-014).

SPEC-003 approved by the founder on 2026-10-07 (all recommendations, Q1–Q7). Next: the design for founder review (amber).

## Context to load
- Spec: `docs/specs/SPEC-003-work-classes.md`
- ADRs: ADR-071, ADR-072, ADR-017, ADR-069, ADR-090, ADR-093, ADR-094, ADR-047
- Code:
  - `backend/src/abacus/kernel/temporal.py`
  - `backend/src/abacus/worker/__main__.py`
  - `backend/src/abacus/modules/connections/retrievals.py` and `workflows.py`
  - `backend/src/abacus/modules/agents/screenings.py`, `spec.py` and `workflows.py`
  - `backend/src/abacus/ai_gateway/__init__.py`
- Reference: `docs/architecture/reference/` (unit of work, backend module); the `temporal-workflow` skill

## Plan
- [ ] Plan approved by human

### Design (for founder review)
Not started: waits for SPEC-003 approval.

### Steps
1. Design and interface contract, after the spec is approved.
2. Implementation.
3. Independent tests (ADR-078), reviews, `make check`, PR.

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
- `2026-10-07` — Created with SPEC-003 (draft) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
- SPEC-003 open questions Q1–Q7.

## Handoff
- **Current state:** SPEC-003 drafted (branch `spec-003-work-classes`); waiting for founder approval.
- **Exact next step:** once SPEC-003 is approved, write the design in *Plan* and stop for approval.
