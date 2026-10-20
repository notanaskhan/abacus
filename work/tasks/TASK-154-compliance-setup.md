---
id: TASK-154
title: "Q-02-T01 · Compliance programme set-up: docs/ops/compliance/README.md gate tracker (M4 and M7 criteria with owner and date), docs/ops/soc2-control-map.md skeleton mapping Security, Availability and Confidentiality controls to ADRs and owners, Qualified Individual designation (notanaskhan, ayushkbhatia deputy), F-01 soc2-risk issue queued for the tool"
spec: SPEC-051
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: amber
status: todo
epic: Q-02
plan_key: Q-02-T01
branch: task-154-compliance-setup
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
Every M4 and M7 criterion has a named owner and date in the tracker, and every control in the map cites at least one ADR and one owner.

## Scope
**In**
- docs/ops/compliance/README.md gate tracker: every M4 and M7 criterion with owner and date
- docs/ops/soc2-control-map.md skeleton mapping Security, Availability and Confidentiality controls to ADRs and owners
- Qualified Individual designation recorded (the builder; the epic's notanaskhan/ayushkbhatia pair collapses under the solo amendment)
- An F-01 soc2-risk issue queued for the compliance tool

**Out**
- Connecting the compliance tool (Q-02-T10)
- WISP, policy set, vendor register (F-09)

## Context to load
- Spec: `docs/specs/SPEC-051-compliance-setup.md` (sections 5 and Task map; ACs AC-1, AC-2, AC-3)
- Epic: `docs/plan/epics/Q-02.md`: Q-02 §0 (summary, decisions table 0.1: DEC-26, DEC-02); Q-02 §10 items 1, 2 and 9; Q-02 §11 R8 (counsel late)
- Task row: `docs/plan/epics/Q-02.tasks.csv`, `Q-02-T01`
- Process: `docs/plan/AMENDMENT-solo.md`
- Data boundary: `docs/specs/SPEC-036-data-boundary.md` (referenced, not duplicated); ADR-113, ADR-114

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Extract the M4 and M7 criteria from Q-02 §10 item 1 and 2 and chapter 01
2. [ ] Write the tracker table with owner and date
3. [ ] Draft the control map with ADR citations
4. [ ] Record the QI designation; open the issue

Files to create or change:
- docs/ops/compliance/README.md
- docs/ops/soc2-control-map.md

Tests to write (mapped to ACs):
- AC-1 -> every tracker row has owner and date
- AC-2 -> every control row cites an existing ADR id and an owner
- AC-3 -> designation present; issue linked

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
