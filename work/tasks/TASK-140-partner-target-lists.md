---
id: TASK-140
title: "F-09-T15 · Partner profile and named target lists per window (audit/EBP 2-3 firms, extension-season tax 1-2 on CCH Axcess, CAS 1 on QBO); outreach to at least 6 firms"
spec: SPEC-049
acceptance_criteria: [AC-26]
risk_zone: green
status: todo
epic: F-09
plan_key: F-09-T15
branch: task-140-partner-target-lists
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
At least 6 conversations are booked by Fri Oct 30 (M1) and each window has a named list of at least 5 firms in the vault.

## Scope
**In**
- Write the partner profile (chapter 01 §1.6.4) and named target lists per window in the vault: audit/EBP 2-3 firms, extension-season tax 1-2 on CCH Axcess, CAS 1 on QBO
- Outreach to at least 6 firms; book conversations
- Keep each window's list at 5 or more named firms

**Out**
- Firm names in git
- Interviews themselves (wave 1)
- Sending an LOI (F-09-T27)

## Context to load
- Spec: `docs/specs/SPEC-049-vendor-legal-assurance-programme.md` (sections: 5 AC-26; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/F-09.md` §0 (lines 11-29), §3 (127-244), §9 (401-674), §10 (675-696), §11 (697-723); read in full: §3.6 F2 (named targets and conversations); §9 row F-09-T15; §10 M1 bullet; §11 R-1
- Row: `docs/plan/epics/F-09.tasks.csv`, plan key F-09-T15
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- Chapter 01 §1.6.4 partner profiles

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is green)

Steps:
1. [ ] Write the profile per window
2. [ ] Build each window's named list (5 or more firms) in the vault
3. [ ] Send outreach to at least 6 firms and book the calls
4. [ ] Record counts and dates in the tracker without naming firms

Files to create or change:
- vault target lists (outside git)
- docs/ops/vendors/README.md (counts and dates only)

Tests to write (mapped to ACs):
- AC-26 → doc check: at least 6 conversations booked by Fri Oct 30 and each window has a vault list of at least 5 firms; no firm name in git

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
- No dependency; start in week 1.
- Auditor and pen-test candidates must never be target-list firms (AC-19).

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Draft the partner profile per window and start the target lists in the vault.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
