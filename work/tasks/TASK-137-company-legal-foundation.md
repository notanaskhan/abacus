---
id: TASK-137
title: "F-09-T02 · Company and legal foundation for M0 (RK-59): formation documents, founder agreement, IP assignment from the builder (and any other contributor), employment-agreement IP and non-solicit check"
spec: SPEC-049
acceptance_criteria: [AC-4]
risk_zone: green
status: todo
epic: F-09
plan_key: F-09-T02
branch: task-137-company-legal-foundation
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
By Fri Oct 23 the formation evidence and the IP assignments are filed in the vault and noted beside DEC-03, or partner contracting is paused.

## Scope
**In**
- File the formation documents, the founder agreement and the IP assignments in the vault
- Check employment-agreement IP and non-solicit terms for every contributor
- Note the filing beside DEC-03 in `docs/product/decision-log.md` (status only, no document content)
- If anything is missing, record that partner contracting is paused until it is signed (RK-59)

**Out**
- Document contents in git
- Counsel engagement (F-09-T04)
- Any partner contract

## Context to load
- Spec: `docs/specs/SPEC-049-vendor-legal-assurance-programme.md` (sections: 5 AC-4; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/F-09.md` §0 (lines 11-29), §3 (127-244), §9 (401-674), §10 (675-696), §11 (697-723); read in full: §3.1 A2 (company foundation); §9 row F-09-T02; §11 R-11
- Row: `docs/plan/epics/F-09.tasks.csv`, plan key F-09-T02
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is green)

Steps:
1. [ ] List what exists: formation documents, founder agreement, IP assignments, employment terms
2. [ ] File each in the vault; note the vault reference only
3. [ ] Add the note beside DEC-03 in the decision log by Fri Oct 23
4. [ ] If an item is missing, record the pause on partner contracting and the date to resolve it

Files to create or change:
- docs/product/decision-log.md (append one status line)
- vault (outside git)

Tests to write (mapped to ACs):
- AC-4 → doc check: the decision-log note exists by Fri Oct 23 and the vault holds every item, or the pause is recorded

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
- Solo edition: one builder, so there is no second founder's assignment to collect; any other contributor still needs one.
- Nothing from the documents goes into git.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Gather the formation documents and the founder agreement into the vault.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
