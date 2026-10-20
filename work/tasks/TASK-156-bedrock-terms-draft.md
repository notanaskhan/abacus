---
id: TASK-156
title: "Q-02-T03 · Draft the Bedrock provider-terms entry for counsel: documents relied on (AWS Customer Agreement, Service Terms, AWS DPA, Bedrock data-protection terms) with versions, region us-east-2 with the US Geo inference profile, training none, no retention beyond processing (invocation logging off), sub-processors, breach notice; draft PR only, never merged before counsel"
spec: SPEC-051
acceptance_criteria: [AC-6, AC-7]
risk_zone: red
status: todo
epic: Q-02
plan_key: Q-02-T03
branch: task-156-bedrock-terms-draft
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
A draft PR against docs/operations/provider-terms.yaml carries every ADR-114 field and is handed to counsel through F-09 with the documents list.

## Scope
**In**
- A draft Bedrock entry against docs/operations/provider-terms.yaml with every ADR-114 field: documents (AWS Customer Agreement, Service Terms, AWS DPA, Bedrock data-protection terms with versions), region us-east-2 with US Geo inference profile, training none, no retention beyond processing (invocation logging off), subprocessors, breach notice
- Hand-off to counsel through F-09 with the documents list; the entry is not merged to main before counsel's review

**Out**
- Second-approver schema change and the live entry (Q-02-T18)
- Route parity report (Q-02-T11)
- Any boundary code (SPEC-036)

## Context to load
- Spec: `docs/specs/SPEC-051-compliance-setup.md` (sections 5 and Task map; ACs AC-6, AC-7)
- Epic: `docs/plan/epics/Q-02.md`: Q-02 §0 (decisions table: DEC-03, SPEC-036 row); Q-02 §7.2 obligations row for ADR-113/114/115 and SPEC-036; Q-02 §10 item 1 (Bedrock entry current, counsel as second approver); ADR-114 and SPEC-036 (referenced, not duplicated)
- Task row: `docs/plan/epics/Q-02.tasks.csv`, `Q-02-T03`
- Process: `docs/plan/AMENDMENT-solo.md`
- Data boundary: `docs/specs/SPEC-036-data-boundary.md` (referenced, not duplicated); ADR-113, ADR-114

## Plan
- [ ] Plan written in this file (required for amber and red)

Steps:
1. [ ] Run first: F-09-T11 (Bedrock access filed) or note the gap
2. [ ] Fetch current versions of the four AWS documents; record title, version, accepted date
3. [ ] Write the entry on the task branch; leave approved_by/approved_on/review_by pending
4. [ ] Run the register tests locally; do not merge; record the F-09 hand-off in the log

Files to create or change:
- docs/operations/provider-terms.yaml (on the task branch only)

Tests to write (mapped to ACs):
- AC-6 -> register test (every entry has every field; compiled module equals YAML) once counsel fields are filled
- AC-7 -> branch unmerged; hand-off recorded

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
