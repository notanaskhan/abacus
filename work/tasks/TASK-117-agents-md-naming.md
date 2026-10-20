---
id: TASK-117
title: "F-02-T03 · ADR-118 (P-01 product naming) plus the AGENTS.md mission, naming, stop-on-open-decision and D1-D10/X-01..X-08 paragraphs (F-01-T02 owns the governance sections and build-plan header)"
spec: SPEC-046
acceptance_criteria: [AC-9, AC-10]
risk_zone: red
status: done
epic: F-02
plan_key: F-02-T03
branch: task-117-agents-md-naming
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
ADR-118 is accepted with notanaskhan's approval and AGENTS.md tells every session to stop when a decision blocking its screen is open.

Solo reading: the product-naming ADR landed as ADR-133 (P-01) and the approval clause is void; the objective is `AGENTS.md` telling every session to stop on an open blocking decision.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-046-decision-day-adr-glossary.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-02.md` section 3.1 (Story A3), section 9 (row F-02-T03), section 10
- Epic tasks CSV: `docs/plan/epics/F-02.tasks.csv` row F-02-T03

## Plan
Steps:
1. [x] Write ADR for P-01 product naming.
2. [x] Add mission, naming, stop-on-open-decision and D1-D10/X-01..X-08 paragraphs to `AGENTS.md`.
3. [x] Dry-run DEC-20 / BND-01.

Files to create or change:
- `docs/adr/ADR-133-product-naming.md`
- `AGENTS.md`

Checks (mapped to ACs):
- AC-9 -> `AGENTS.md` text
- AC-10 -> dry run

## Definition of done
- [x] Every listed AC is satisfied and the file or section that satisfies it is cited in the progress log
- [x] `cd backend && uv run python -m abacus_tools.quality.validate_docs` passes
- [x] No secrets or real client data committed
- [x] Decisions recorded in `docs/product/decision-log.md` or an ADR

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

- `2026-10-20` — Done in SU-08 (2026-10-20), commits 82f1511 and 69dfc7e

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- The plan's ADR-118 is ADR-133 in this repo (numbers are next-free).

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Done in SU-08.
- **Exact next step:** None; re-run validate_docs if either file is edited again.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** Boxes ticked from the SU-08 record, not re-verified here.
