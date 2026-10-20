---
id: TASK-155
title: "Q-02-T02 · docs/architecture/ai-threat-model.md (ADR-064): assets, trust boundaries (gateway, Bedrock route, tool layer, portal), hostile-content and prompt-injection paths, cross-tenant and TRI exposure, each mitigation mapped to a test or ADR; notanaskhan reviews"
spec: SPEC-051
acceptance_criteria: [AC-4, AC-5]
risk_zone: amber
status: todo
epic: Q-02
plan_key: Q-02-T02
branch: task-155-ai-threat-model
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
The threat model merges with every listed threat mapped to an existing or planned test, and notanaskhan's review is recorded.

## Scope
**In**
- docs/architecture/ai-threat-model.md: assets; trust boundaries (gateway, Bedrock route, tool layer, portal); hostile-content and prompt-injection paths; cross-tenant and TRI exposure
- Every mitigation mapped to an existing or planned test, or an ADR
- Self-review recorded (security reviewer subagent, optional per solo amendment)

**Out**
- Writing the mapped tests
- Changing the gateway or tool layer

## Context to load
- Spec: `docs/specs/SPEC-051-compliance-setup.md` (sections 5 and Task map; ACs AC-4, AC-5)
- Epic: `docs/plan/epics/Q-02.md`: Q-02 §0 (supporting-founder row: AI threat model, chapter 08 §8.1.1); Q-02 §6.1 (capabilities, tools and gates) and §7.2 obligations rows for ADR-113/114/115; Q-02 §10 item 9; ADR-064
- Task row: `docs/plan/epics/Q-02.tasks.csv`, `Q-02-T02`
- Process: `docs/plan/AMENDMENT-solo.md`
- Data boundary: `docs/specs/SPEC-036-data-boundary.md` (referenced, not duplicated); ADR-113, ADR-114

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Read ADR-064 and ADR-113; list assets and boundaries
2. [ ] Enumerate threats; map each to a test path or ADR
3. [ ] Self-review; record in the file

Files to create or change:
- docs/architecture/ai-threat-model.md

Tests to write (mapped to ACs):
- AC-4 -> each threat row names an existing test path, a planned task id or an ADR
- AC-5 -> review note present

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
