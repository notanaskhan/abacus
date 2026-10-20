---
id: TASK-120
title: "F-02-T06 · M1 orphan ADR drafts: ADR-125 (P-26) e-signature, P-17 write-capability framework and P-29 busy-season policy, the last two numbered from ADR-131 when drafted (status proposed, counsel review requested for P-26)"
spec: SPEC-046
acceptance_criteria: [AC-18, AC-19, AC-20, AC-21, AC-22]
risk_zone: red
status: todo
epic: F-02
plan_key: F-02-T06
branch: task-120-m1-orphan-adrs
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
Three ADR files merge as proposed by Fri Oct 30 and backlog.md records their numbers and accept-by dates: Nov 27 (P-17), Dec 4 (P-26) and the Dec 14-18 bundle (P-29).

Solo reading: numbers are the next free number on `main`, recorded in `backlog.md`; ADR-125 is a plan number only.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-046-decision-day-adr-glossary.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-02.md` section 3.2 (Story B4), section 9 (row F-02-T06), section 10, section 11 (R-13, R-14)
- Epic tasks CSV: `docs/plan/epics/F-02.tasks.csv` row F-02-T06

## Plan
Steps:
1. [ ] Write the plan here (red zone): outline each ADR from the Story B4 text.
2. [ ] Draft P-26, P-17 and P-29 as `proposed` ADR files.
3. [ ] Record numbers and accept-by dates in `backlog.md`; add README rows.
4. [ ] Run validate_docs.

Files to create or change:
- Three new files in `docs/adr/`
- `docs/adr/backlog.md`
- `docs/adr/README.md`

Checks (mapped to ACs):
- AC-18 -> P-26 content
- AC-19 -> counsel request/fallback
- AC-20 -> P-17 content
- AC-21 -> P-29 content
- AC-22 -> validate_docs, backlog dates

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

- (none yet)

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- Depends on TASK-116. Fallback for P-26 is record mode only.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
