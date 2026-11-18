---
id: TASK-8632
title: "T-06-T21: Relationship service in organisations"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: t06-t21-relationship-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T21
---

## Objective
Spec section: docs/plan/epics/T-06.md §3 F8, §4.3. Create, update and end with validation (no self-edge, ownership at most 100 percent, effective dates), external parties, walls with 404 and no counts, audited relationship.created/updated/ended; a fail-closed register_relationship_annotator slot.

## Plan (red)
1. organisations/relationships.py: create (self-edge 422; ownership cap computed in code on every start day, 0954's deferred trigger behind it; entity or external party on either side), update (expected_version; cap re-checked with the edge's new percent), end (end date and reason; never deleted), add_external_party; insert-only events with on_behalf_of from the session; audit relationship.created/updated/ended and external_party.created; register_relationship_annotator.
2. Exported via organisations.api.
3. tests/unit/organisations/test_t06t21_relationships.py: 60 + 40 fills, +1 exceeds; an ended period frees its percent; non-ownership edges never count.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5632). Partial: the graph and list projection and the C-03 routes in relationships_contract.py wire up with CLI-03's screen task (T-06-T41, after the CLI-03 board, T-06-T02 blocked); per-user layouts with it. The caller authorises the client (walls 404) before calling. Gates and tests run once at the S50 end pass (build first, test last).
