---
id: TASK-139
title: "F-09-T14 · Discovery thresholds W1-W3 (and the build-plan section 4.1 blanks) in docs/product/discovery/thresholds.md before the first call; interview guide covering ledger, tax engine, e-signature, mailbox, Google or M365, PHI exposure, SQMS needs and pricing; anonymisation rules"
spec: SPEC-049
acceptance_criteria: [AC-25, AC-27]
risk_zone: green
status: todo
epic: F-09
plan_key: F-09-T14
branch: task-139-discovery-thresholds
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
thresholds.md merges before the first call and the guide covers the inputs to DEC-25, DEC-49, DEC-70, DEC-75 and proposed DEC-100.

## Scope
**In**
- Write `docs/product/discovery/thresholds.md` with W1-W3 (and fill the build-plan §4.1 blanks to point at it) before the first call
- Write the interview guide covering ledger, tax engine, e-signature, mailbox, Google or M365, PHI exposure, SQMS needs and pricing
- Write the anonymisation rules (firm codes only; no client data, DEC-05)

**Out**
- W4-W8 thresholds (merge before Mon Jan 11, 2027)
- Holding the interviews (wave 1)
- Loosening any threshold later

## Context to load
- Spec: `docs/specs/SPEC-049-vendor-legal-assurance-programme.md` (sections: 5 AC-25, AC-27; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/F-09.md` §0 (lines 11-29), §3 (127-244), §9 (401-674), §10 (675-696), §11 (697-723); read in full: §3.6 F1 (thresholds first), F2 (named targets and conversations); §9 row F-09-T14; §10 M1 bullet
- Row: `docs/plan/epics/F-09.tasks.csv`, plan key F-09-T14
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- Chapter 11 §11.6.1: thresholds are written down before the evidence arrives
- `docs/product/build-plan.md` §4.1 (three blanks) and `docs/product/discovery/` as they stand when you start

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is green)

Steps:
1. [ ] Draft W1-W3 from chapter 11 §11.6.1 with exact numbers from the plan
2. [ ] Merge thresholds.md before the first call is held; point the build-plan §4.1 blanks at it
3. [ ] Write the guide so it yields the inputs to DEC-25, DEC-49, DEC-70, DEC-75 and proposed DEC-100
4. [ ] Write the anonymisation rules into the guide

Files to create or change:
- docs/product/discovery/thresholds.md (new)
- docs/product/discovery/interview-guide.md (new)
- docs/product/build-plan.md (§4.1 blanks point to thresholds.md)

Tests to write (mapped to ACs):
- AC-25 → doc check: thresholds.md merged before the first call; guide covers the listed topics and the five decisions
- AC-27 → doc check: the guide states firm-code-only notes and no client data

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
- Depends on F-09-T01.
- Thresholds may be tightened later, never loosened.
- Other sessions edit `docs/product/` at setup time; start this task after they have finished.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Read chapter 11 §11.6.1 and draft W1-W3.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
