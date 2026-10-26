---
id: TASK-1402
title: Decision cards service, raise, read, decide, notify, analysis requests and reassess (P-04-T23)
spec: SPEC-360
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T23
branch: s11-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The decision-card routes answer 501. Serve them: `review.api.raise_decision_card` (the agent
through `task_scope`), options from the kind's provider (code computes), GET card with versions,
POST decide (reserved role, rationale required, seen version, MFA per kind), notify, recorded
analysis requests, reassess to No change or a superseding card, DECISION-001, and a platform test
kind with the Northwind materiality golden. Acceptance: only Margaret Okonkwo can decide the
Northwind card, a decide without a rationale returns 422 `rationale_required`, and reassessment on
$16,861,000 records No change with the $700 difference.

## Plan
- **Migration 0211** (`0211_decision_card_history`, down 0210): insert-only
  `decision_card_versions` (proposed, decided, reassessed; figures; human-only decided and
  reassessed rows), insert-only human-only `decision_analysis_requests` (sealed text); the app
  may insert `decisions.id` (the rationale seal is bound to it). Forced RLS, immutable triggers.
- **Slot** `DecisionKind`: `compute(tenant, engagement_id, work_item_id) -> ComputedCard`
  (question, context, options with figures, factors), `reassess(...) -> Reassessment` (changed,
  figures, recomputed card), `mfa_max_age_s` (default 900; None opts out).
- **Service** `review/decisions.py`: `raise_decision_card` (agent `task_scope` or a person
  allowed `decision_card.raise`; options from the provider; agent recommendation as a flagged
  option and the suggestion id, never the decider); `list_cards` (`visible(decision.read)`),
  `card_detail` (rationale read is an access event), `decide_card` (live human, `decision.decide`
  with the card's reserved role and person, MFA per kind 403 `mfa_required`, 409
  `recommendation_changed`, 422 `rationale_required`, sealed rationale, `decision.decided`
  audit and outbox), `request_analysis` (sealed text), `notify` (mention to the reserved
  person), `reassess` (provider recomputes; no change is a new version, a change supersedes).
- **Matrix**: `decision_card.raise: {agent: task_scope}`. **DECISION-001**: only
  `review/decisions.py`, `review/contract.py` and `review/api.py` name `decide_card`.
- **Notifications**: `decision_card.raised` -> `decision_assigned`; notify -> `mention`.
- **Tests first**: `tests/integration/test_p04t23_decision_cards.py` (a test kind computing the
  Northwind golden: 16,812,400 at 1.5% -> 252,200, PM 189,150, CT 12,610; 16,861,000 -> 252,900,
  difference 700).
- **Rollback**: revert and downgrade 0211.

## Progress log
- 2026-10-27: planned.
- 2026-10-27: built (acceptance tests written first, run in the end-of-batch targeted pass). Decisions DEC-500 to DEC-504; ED-150. Generated client and matrix regenerated.
- 2026-10-27: security-review fix round (merged origin/main ee7bdf04; 0210 now revises 0197): migration 0213 status guards, fresh MFA on sign_off.create and decision.decide, serialised idempotency keys, decided-card reassess by the decider, suggestion and work-item ownership checks (DEC-505, DEC-506).
