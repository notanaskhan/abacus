---
id: TASK-121
title: "F-02-T13 · ADR-127 (P-37) clock, scenario loader and synthetic marker, drafted from chapter 03 text for F-04 (DEC-27)"
spec: SPEC-046
acceptance_criteria: [AC-23, AC-24]
risk_zone: amber
status: done
epic: F-02
plan_key: F-02-T13
branch: task-121-adr-clock-scenario
created: 2026-10-20
updated: 2026-10-25
---

> Solo edition. Write the plan below first (amber and red), then build. If scope must change, stop and add it to Questions. Append to the Progress log before ending a session.

## Objective
ADR-127 is open by Tue Oct 27 and accepted with both handles by Fri Oct 30, before F-04-T02 starts in S1, and backlog.md marks it accepted.

Solo reading: accepted by the builder (sole decider); number is the next free number, recorded in `backlog.md`.

## Scope
**In**
- The deliverables named under Files to create or change, satisfying the listed ACs

**Out**
- Anything not needed by the listed ACs
- Meetings, approvals, reservation issues and number blocks (void under the solo amendment)

## Context to load
- Spec: `docs/specs/SPEC-046-decision-day-adr-glossary.md`
- Plan: `docs/plan/AMENDMENT-solo.md` (overrides process)
- Epic: `docs/plan/epics/F-02.md` section 3.2 (Story B4, last bullet), section 9 (row F-02-T13)
- Epic tasks CSV: `docs/plan/epics/F-02.tasks.csv` row F-02-T13

## Plan
Steps:
1. [ ] Draft P-37 from chapter 03's clock text by Tue Oct 27.
2. [ ] Accept it by Fri Oct 30 and mark it accepted in `backlog.md`.
3. [ ] Run validate_docs.

Files to create or change:
- New file in `docs/adr/`
- `docs/adr/backlog.md`
- `docs/adr/README.md`

Checks (mapped to ACs):
- AC-23 -> content
- AC-24 -> dates and backlog status

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
- `2026-10-25` — S8b verification. P-37 = ADR-143, `accepted` 2026-10-20 (before Tue Oct 27 and Fri Oct 30), and `backlog.md` marks it accepted (AC-24). AC-23: the ADR records `kernel.clock` with production refusal, the demo clock on synthetic tenants only, `scenarios/brightwater_hale` replaying through service APIs, and `firms.synthetic` replacing the "(Synthetic)" suffix. It names the module, not its four functions; `now`, `today`, `system_now` and `frozen` are in `backend/src/abacus/kernel/clock.py`. The ADR is accepted, so it is not edited (a supersede for wording alone is not worth a new number). Done.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| | | |

## Gotchas and discoveries
- Depends on TASK-116. Red parts never default on silence.

## Questions for the human
- [ ] None.

## Handoff
- **Current state:** done: ADR-143 accepted and indexed.
- **Exact next step:** none.
- **Uncommitted or partial work:** None.
- **Known failing checks:** None.
- **Open issues:** None.
