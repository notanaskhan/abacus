---
id: TASK-115
title: "F-02-T01 · Decision register: docs/product/decision-log.md with DEC-01..DEC-99 plus proposed DEC-100/101 (chapter 01 effective dates, owners, never-default flags), decision label, issues DEC-01..DEC-19 once the repo is private"
spec: SPEC-046
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: green
status: in-progress
epic: F-02
plan_key: F-02-T01
branch: task-115-decision-log
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
decision-log.md lists 101 rows with owner, effective decide-by, default eligibility and status, and issues DEC-01..DEC-19 exist with the recommended answer pasted.

Solo reading: issues are optional (the log is the binding index); AC-3 only forbids opening any while the repository is public.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-046-decision-day-adr-glossary.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-02.md` section 3.1 (Story A1), section 9 (row F-02-T01), section 10, section 11 (R-02, R-12)
- Epic tasks CSV: `docs/plan/epics/F-02.tasks.csv` row F-02-T01

## Plan
Steps:
1. [ ] Verify the SU-12 output: 101 rows, every column filled (AC-1).
2. [ ] Verify never-default rows (AC-2).
3. [ ] Confirm no issue was opened while public (AC-3).
4. [ ] Fix gaps; run validate_docs.

Files to create or change:
- `docs/product/decision-log.md`

Checks (mapped to ACs):
- AC-1 -> count rows and columns
- AC-2 -> listed DEC rows read "never defaults"
- AC-3 -> no issues opened

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
- `docs/product/` is being edited by other sessions; do not touch it from this planning step.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Created in SU-12 (2026-10-20); not yet verified against the ACs.
- **Exact next step:** Verify AC-1 to AC-3 against `docs/product/decision-log.md`.
- **Uncommitted or partial work:** None known.
- **Known failing checks:** None.
- **Open issues:** None.
