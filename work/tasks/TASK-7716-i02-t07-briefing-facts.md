---
id: TASK-7716
title: I-02-T07 Briefing facts collector (agents/briefing/facts.py)
plan_key: I-02-T07
spec: SPEC-654
acceptance_criteria: [AC-3.1, AC-3.2]
risk_zone: red
status: in-review
branch: i02-t07-briefing-facts
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Code gathers, per engagement and viewer, the gates, registered facts, candidate citations and
§7216 subjects a `briefing.today` run may use, with a stable hash and consent checked first.

## Plan (red)
- `agents/briefing/facts.py` (new), `agents/api.py` exports, `review/api.py` exports
  (`gates_waiting_on`, `gate_counts`, `GateCounts`), `tax/briefing_source.py` + registration.
- Tests: `backend/tests/unit/briefing/test_i02t07_briefing_facts.py`.
- Rollback: revert; no caller until I-02-T08.

## Partial
- Engagements' G1–G3 facts and work-item milestones join through I-02-T11's attention providers;
  recommendations and proposals on the gates (P-04's) are referenced by the gate rows, not read
  as separate facts here.
- Candidate citations are offered, not verified: T-08's validator verifies the ones used.
- "8 gates" at E0 depends on the scenario's gates for Ridgeline (the end-pass load).

## Progress log
- 2026-11-13: built; registration checked at import; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4719 | collector, slot, consent-first and hash | no |
