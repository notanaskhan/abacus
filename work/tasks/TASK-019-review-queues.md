---
id: TASK-019
title: Review queues and review decisions
spec: SPEC-004
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14]
risk_zone: red
status: blocked
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
Implement SPEC-004.
- **The queue:** evidence awaiting a human's judgement is queued per engagement, and a reviewer takes it.
- **The decision:** the reviewer records a review decision (accept, reject or send back). Reject and send back require a reason code. Decisions are human-only (ADR-005), insert-only and audited.
- **For the Learning layer:** decisions, reason codes and corrections of the agent's proposal are stored.

## Scope
All of SPEC-004 (AC-1 to AC-14), once approved.

Excluded:
- the learning loop (ADR-068);
- follow-ups on send-back (increment 8);
- suggestions beyond screening results;
- reopening accepted items;
- sign-off workflows;
- firm settings.

**Blocked on SPEC-004 approval** (open questions Q1–Q8).

## Context to load
- **Spec:** `docs/specs/SPEC-004-review-queues.md`
- **ADRs:** ADR-005, ADR-054, ADR-004, ADR-007, ADR-020, ADR-026, ADR-027, ADR-031, ADR-061, ADR-068, ADR-102
- **Code:**
  - `backend/src/abacus/modules/evidence/` (versions, routes)
  - `backend/src/abacus/modules/requests/` (item statuses)
  - `backend/src/abacus/modules/agents/` (screening results, the handoff)
  - `backend/src/abacus/modules/identity/authz/`
  - `docs/architecture/permission-matrix.yaml`
- **Reference:** `docs/architecture/reference/` (backend module, tenancy and authz, unit of work); the `backend-module` skill

## Plan
- [ ] Plan approved by human

### Design (for founder review)
Not started: waits for SPEC-004 approval.

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
- `2026-10-07` — Created with SPEC-004 (draft) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Gotchas and discoveries
-

## Questions for the human
- SPEC-004 open questions Q1–Q8.
- Glossary entries "review queue" and "reason code" (protected).

## Handoff
- **Current state:** SPEC-004 drafted (branch `spec-004-review-queues`); waiting for founder approval.
- **Exact next step:** once SPEC-004 is approved, write the design in *Plan* and stop for approval.
