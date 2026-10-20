---
id: TASK-118
title: "F-02-T04 · Glossary change-set PR (DEC-14, chapter 09 section 9.5): header rules, 24 amendments, reserved words, additions, legacy rename/freeze table, status-bridge pointer, Abacus entry"
spec: SPEC-046
acceptance_criteria: [AC-11, AC-12, AC-13, AC-14]
risk_zone: red
status: done
epic: F-02
plan_key: F-02-T04
branch: task-118-glossary
created: 2026-10-20
updated: 2026-10-20
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
glossary.md merges by Fri Oct 30 with notanaskhan's approval, every section 9.5 row present and Don't-use columns machine-readable.

Solo reading: the approval clause is void; the file must still land by Fri Oct 30 and before F-03's first Accrued backend PR.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-046-decision-day-adr-glossary.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-02.md` section 3.3 (Stories C1, C2), section 9 (row F-02-T04), section 10, section 11 (R-07, R-16); chapter 09 section 9.5 for the change set
- Epic tasks CSV: `docs/plan/epics/F-02.tasks.csv` row F-02-T04

## Plan
Steps:
1. [ ] Write the plan here (red zone): map each chapter 09 section 9.5 subsection to a glossary section.
2. [ ] Edit `docs/product/glossary.md`: header rules, 24 amendments, reserved words, additions grouped by module, legacy table, status-bridge pointer, copy-ban index, Abacus entry.
3. [ ] Add the four DEC-14 statements and make Don't-use columns machine-readable.
4. [ ] Run validate_docs.

Files to create or change:
- `docs/product/glossary.md`

Checks (mapped to ACs):
- AC-11 -> checklist against section 9.5
- AC-12 -> four statements
- AC-13 -> columns parse
- AC-14 -> merged before first F-03 backend PR

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
- 2026-10-20 (SU-25): glossary change set applied: §9.5.1 header rules, 25 amended rows, reserved words, 105 additions in 26 module sections, the legacy rename and freeze table, copy-level bans, the Evidence board label (R-07), machine-readable Don't use cells. glossary_report.py prints the counts (150 terms, 101 Don't use entries). The §9.5.6 status bridge lives in the status registry.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- Depends on TASK-117 (`AGENTS.md`). Legacy `reminders`/`reminder_items` stay until F-03-T16, dated exception expiring Fri Nov 27, 2026.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** Not started.
- **Exact next step:** Read the Objective, then step 1.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
