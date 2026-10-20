---
id: TASK-119
title: "F-02-T05 · Decision Day Fri Oct 23 (M0): agenda pack Thu Oct 22 with drafts linked, outcomes and owners recorded, default-on-silence applied, chapter 01 amendments and the parity-tier reading recorded, P-64..P-69 confirmed, ADR-numbering erratum issued"
spec: SPEC-046
acceptance_criteria: [AC-15, AC-16, AC-17]
risk_zone: green
status: todo
epic: F-02
plan_key: F-02-T05
branch: task-119-decision-day
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
Every Block A row is decided and every Block B row has an owner and date in decision-log.md, decided issues are closed against their artefact, chapter 09 section 9.4.2 gains rows P-64..P-69 (or records their rejection), and chapter 01 sections 1.2.1 and 1.3.3 carry the parity-tier wording decided.

Solo reading: Decision Day is a solo decision session (SU-12): no meeting; decide each row using the plan's recommended option as default and record it in `docs/product/decision-log.md` or an ADR.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-046-decision-day-adr-glossary.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-02.md` section 3.1 (Story A2 and the agenda table, Blocks A, B, C), section 9 (row F-02-T05), section 10 (M0), section 11 (R-05, R-06, R-13, R-15)
- Epic tasks CSV: `docs/plan/epics/F-02.tasks.csv` row F-02-T05

## Plan
Steps:
1. [ ] Assemble the agenda pack from the section 3.1 table, linking each draft.
2. [ ] Work Block A: decide each row; record artefact.
3. [ ] Work Block B: owner and date per row.
4. [ ] Work Block C: record the five amendments, parity-tier reading, P-64 to P-69 and the erratum.
5. [ ] Update decision-log.md; run validate_docs.

Files to create or change:
- `docs/product/decision-log.md`
- chapter 01 and chapter 09 edits as Block C names

Checks (mapped to ACs):
- AC-15 -> pack links
- AC-16 -> walk the blocks
- AC-17 -> artefact links

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
- Never-default rows (money, contract, counsel, red ADR) stay open until recorded.
- Depends on TASK-115 and TASK-116.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
