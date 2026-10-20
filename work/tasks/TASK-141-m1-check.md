---
id: TASK-141
title: "F-09-T17 · The builder's own M1 check of F-09's S0 exit: every application filed, counsel engaged, compliance tool chosen, at least 6 conversations booked"
spec: SPEC-049
acceptance_criteria: [AC-33, AC-8, AC-18, AC-22, AC-26]
risk_zone: green
status: todo
epic: F-09
plan_key: F-09-T17
branch: task-141-m1-check
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan below into this file first, then build.
> - If scope must change, add it to *Questions for the human* and carry on with the plan's proposed option.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
The builder records the M1 result in decision-log.md on Fri Oct 30, naming any unfiled application with a date.

## Scope
**In**
- On Fri Oct 30 walk the M1 list: every §7.6 application has a submitted date, counsel is engaged with a dated scope, the compliance tool is contracted, at least 6 conversations are booked, thresholds W1-W3 merged before the first call
- Record the result in `docs/product/decision-log.md`
- Name any unfiled application with a new date

**Out**
- Fixing a missing item (file a follow-up row instead)
- Anything after M1

## Context to load
- Spec: `docs/specs/SPEC-049-vendor-legal-assurance-programme.md` (sections: 5 AC-33, AC-8, AC-18, AC-22, AC-26; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/F-09.md` §0 (lines 11-29), §3 (127-244), §9 (401-674), §10 (675-696), §11 (697-723); read in full: §10 M1 bullet; §9 row F-09-T17 (rewritten here as the builder's own check); §3.2 B1; §3.3 C1; §3.4 D1; §3.6 F2
- Row: `docs/plan/epics/F-09.tasks.csv`, plan key F-09-T17
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- Rewritten row: the plan's independent M1 record by the other founder becomes the builder's own check (solo amendment)

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is green)

Steps:
1. [ ] Open the tracker and tick each M1 item against its evidence in the tracker or vault
2. [ ] Record the result and any unfiled application with a date in the decision log
3. [ ] Create follow-up tracker rows for each gap

Files to create or change:
- docs/product/decision-log.md (M1 record)
- docs/ops/vendors/README.md (status updates)

Tests to write (mapped to ACs):
- AC-33 → doc check: M1 record present on Fri Oct 30 naming gaps with dates
- AC-8 → every S0 application has a submitted date
- AC-18 → compliance tool contracted by Fri Oct 30
- AC-22 → counsel engaged with a dated, gate-batched scope
- AC-26 → at least 6 conversations booked

## Definition of done
- [ ] Every listed AC is met and has evidence (tracker row, vault record or decision-log entry), referenced by its AC id
- [ ] `cd backend && uv run python -m abacus_tools.quality.validate_docs` passes
- [ ] No price, contract text, partner firm name, counsel advice or secret is in git (the repo is public until F-01-T01)
- [ ] No code changed; no new dependencies
- [ ] Decisions below recorded in `docs/product/decision-log.md` where they bind later work

Commands:
```
cd backend && uv run python -m abacus_tools.quality.validate_docs
```

## New dependencies
| Package | Version | Why | Decision |
|---|---|---|---|
| none | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Task file written at kickoff (SU-14). No work started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | yes / no |

## Gotchas and discoveries
- Depends on F-09-T01, F-09-T04, F-09-T13 and F-09-T15.
- Do the check against evidence, not memory.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** On Fri Oct 30 open the tracker and start the M1 list.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
