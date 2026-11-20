---
id: TASK-8821
title: "Q-05-T16: Firm-scope decision cards (part 2 of 2)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q05t16b
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T16
---

## Objective
Thomas Whitcombe reads Bayside's archive and activity read-only during INS-26-02 and loses access at conclusion, a walled inspector sees nothing, and only Margaret Okonkwo can decide the evaluation card.

## Done
- Migration 0996: decision_cards.scope_kind (engagement | firm), engagement_id nullable only for firm cards, reserved_role += qm_ultimate, CHECK that a firm card has no work item and a named qm_ultimate decider
- review/firm_cards.py: raise_firm_card (quality.manage), decide_firm_card (the named person only, live, fresh MFA, quality_evaluation.decide, one decision, sealed rationale bound to its row)
- matrix row quality_evaluation.decide (quality_partner only) + regenerated _matrix.py and actions.gen.ts
- registry insert column; review.api exports; unit tests

## Progress log
- `2026-11-20` — Plan (red): migration, service, matrix; rollback revert + downgrade 0996. The qm_annual_evaluation kind is registered and raised by practice in Q-05-T18.
