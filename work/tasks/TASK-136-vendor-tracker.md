---
id: TASK-136
title: "F-09-T01 · Programme set-up: docs/ops/vendors/README.md tracker with one row and one vendor issue per chapter 06 section 7.6 application (opened only after the repo is private), document vault outside git for contracts, quotes, LOIs and counsel advice, RK-01/04/05/47/50/59 issues"
spec: SPEC-049
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: todo
epic: F-09
plan_key: F-09-T01
branch: task-136-vendor-tracker
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
Every chapter 06 section 7.6 row has an owner, start date, needed-by date and fallback, and git holds no price, contract text, partner firm name or counsel advice.

## Scope
**In**
- Create `docs/ops/vendors/README.md`: one row per chapter 06 §7.6 application with owner, start, typical lead time [verify], needed-by date, fallback, linked decision and vault reference
- Open one GitHub issue per row labelled `vendor`, only after F-01-T01 makes the repo private
- Set up the document vault outside git for contracts, quotes, LOIs and counsel advice
- Open the RK-01, RK-04, RK-05, RK-47, RK-50 and RK-59 issues

**Out**
- Submitting any vendor application (the builder does that by hand from the SU-26 checklist)
- Any price, contract text, partner firm name or counsel advice in git
- Any issue or commit while the repo is still public

## Context to load
- Spec: `docs/specs/SPEC-049-vendor-legal-assurance-programme.md` (sections: 5 AC-1, AC-2, AC-3; 6; 12; 21 Task map)
- Epic: `docs/plan/epics/F-09.md` §0 (lines 11-29), §3 (127-244), §9 (401-674), §10 (675-696), §11 (697-723); read in full: §3.1 A1 (programme spine) and the vendor table it cites, chapter 06 §7.6; §9 row F-09-T01; §10 M1 bullet; §11 R-3
- Row: `docs/plan/epics/F-09.tasks.csv`, plan key F-09-T01
- Amendment: `docs/plan/AMENDMENT-solo.md` (solo overrides)
- Vault: outside git (path recorded privately; do not write it in the repo)

## Plan
- [ ] Plan written into this file before any build step (required for amber and red; zone is green)

Steps:
1. [ ] Confirm F-01-T01 (repo private) is done; if not, draft the tracker in the vault only (AC-3)
2. [ ] Create the tracker table from chapter 06 §7.6 with the AC-1 columns
3. [ ] Open the `vendor` issues and RK issues; link each row to its issue and decision
4. [ ] Create the vault and add a vault-reference column entry per row
5. [ ] Search the repo for prices, partner firm names and counsel advice; confirm none (AC-2)

Files to create or change:
- docs/ops/vendors/README.md (new)
- GitHub issues labelled `vendor` (new)
- vault (outside git)

Tests to write (mapped to ACs):
- AC-1 → doc check: every §7.6 row has owner, start, needed-by and fallback, and a `vendor` issue
- AC-2 → repo search finds no price, contract text, partner firm name or counsel advice; tracker holds only status, dates and a vault reference
- AC-3 → no tracker file or issue exists dated before F-01-T01 landed

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
- Depends on F-01-T01 (repo private) before any issue or commit.
- Counsel advice stays out of git to protect privilege; vendor terms are often confidential.

## Questions for the human
- [ ] None at kickoff.

## Handoff
Fill this in whenever a session ends before the task is done.
- **Current state:** not started.
- **Exact next step:** Check F-01-T01 status, then create the tracker from the chapter 06 §7.6 vendor table.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** none.
