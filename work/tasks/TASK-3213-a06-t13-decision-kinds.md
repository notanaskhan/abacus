---
id: TASK-3213
title: A-06-T13 decision kinds deficiency_severity and sum_conclusion
spec: SPEC-642
acceptance_criteria: [AC-5, AC-8]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T13
branch: s26-a06-t13 (stacked on s26-a05-t22)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Margaret Okonkwo's decision concludes F-01 as Significant deficiency and the SUM as immaterial,
each card freezes its snapshot, and the HOME-02 projection shows both as Decisions."

## Plan (amber)
- `assurance/completion_decisions.py`:
  - `deficiency_severity`: options by code; the applier concludes the deficiency with the card
    and decision in the decider's unit of work (0644's guard checks the person's decision).
  - `sum_conclusion`: over the newest frozen conclusion snapshot; the card carries its id and
    hash; the applier refuses a changed snapshot (409 `snapshot_changed`).
  - Both are reserved to the engagement partner, with the kind's fresh MFA.
- Routes: `POST /findings/{id}/request-decision` and `…/sum/request-conclusion` are live.
- Tests: `tests/unit/assurance/test_a06t13_decision_kinds.py`.

## Progress log
- 2026-11-03: built. Partial:
  - the SUM snapshot route and qualitative factors (`sum/snapshots`, `qualitative-factors` stay
    501), so a conclusion needs a snapshot written by A-06's SUM service when it lands;
  - human-gate kinds for HOME-02 (C3's card already lists on HOME-02 as a Decision);
  - the `governance_communication.sent` consumer and the notification kinds (A-07).
  Tests at the S26 end review.

## Decisions made during this task
DEC-2213.
