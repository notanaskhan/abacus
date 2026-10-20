---
id: TASK-116
title: "F-02-T02 · ADR programme: docs/adr/backlog.md (P-01..P-69 with drafter, approver, owning epic, number, draft and accept-by sprints); ADR-116..130 reserved by issue on Mon Oct 19 in chapter 09 order (chapter 08 section 8.3.3 rule 5); later numbers minted at drafting from the drafter's block; _TEMPLATE.md deciders note"
spec: SPEC-046
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: green
status: in-progress
epic: F-02
plan_key: F-02-T02
branch: task-116-adr-backlog
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
backlog.md has 69 rows, ADR-116..130 each have an ADR-nnn issue mapped as chapter 08 rule 5, every other row names its block and is filled in when drafted, and validate_docs stays green.

Solo reading: no reservation issues and no number blocks; ADR numbers are the next free number on `main`, and `backlog.md` is the only source.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-046-decision-day-adr-glossary.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-02.md` section 3.2 (Stories B1, B2), section 4.6 (backlog shape), section 9 (row F-02-T02), section 11 (R-03, R-04)
- Epic tasks CSV: `docs/plan/epics/F-02.tasks.csv` row F-02-T02

## Plan
Steps:
1. [ ] Verify the SU-12 output: 69 rows (AC-4).
2. [ ] Check the only-source and burn rules (AC-5, AC-7).
3. [ ] Confirm README rows only for existing ADR files and validate_docs green (AC-6).
4. [ ] Check accept-by dates (AC-8).

Files to create or change:
- `docs/adr/backlog.md`

Checks (mapped to ACs):
- AC-4 -> 69 rows
- AC-5 -> grep specs for stray ADR numbers
- AC-6 -> validate_docs
- AC-7 -> withdrawn marking
- AC-8 -> accept-by sprint rule

## Definition of done
- [ ] Every listed AC is satisfied and the file or section that satisfies it is cited in the progress log
- [ ] `cd backend && uv run python -m abacus_tools.quality.validate_docs` passes
- [ ] No secrets or real client data committed
- [ ] Decisions recorded in `docs/product/decision-log.md` or an ADR

Commands:
```
cd backend && uv run python -m abacus_tools.quality.validate_docs
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — Created in SU-12 (2026-10-20); verify

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- `docs/adr/` is being edited by other sessions; ADR-133, 135, 136, 138 and 139 already exist on disk.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Created in SU-12 (2026-10-20); not yet verified against the ACs.
- **Exact next step:** Verify AC-4 to AC-8 against `docs/adr/backlog.md`.
- **Uncommitted or partial work:** None known.
- **Known failing checks:** None.
- **Open issues:** None.
