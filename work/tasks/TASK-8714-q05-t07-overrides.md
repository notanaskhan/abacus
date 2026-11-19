---
id: TASK-8714
title: "Q-05-T07: Override-rate projection and the agent-overrides reads"
spec: SPEC-711
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
branch: q05-t07-overrides
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T07
---

## Objective
agent_output_outcomes fed by an idempotent outbox consumer (review_decision.recorded, proposal.decided, checkpoint.approved/rejected, proposed_entry.decided events that name their agent output; keyed by event id, so a replay writes nothing), a rebuild for back-fills, and GET /v1/quality/agent-overrides (window, office) and /{agent_key}/reasons computed by compute/override_rates.py (rated from 25, exact-decimal tolerance from the published AI policy, 8% default).

## Plan (amber)
1. practice/compute/override_rates.py (pure) and practice/overrides.py (consumer, rebuild, reads).
2. practice/jobs.py SUBSCRIPTIONS gains the five decision events.
3. quality_contract: two routes call the service.
4. Tests: tests/unit/practice/test_q05t07_override_rates.py.

## Progress log
- `2026-11-19` — Built; tests pass (3). Partial: the decision events' payloads must carry agent_key, outcome, source_id and decided_at for the consumer to project them (events that do not are skipped, never guessed); the producers add those fields with their owners' tasks. The accuracy route (draft-vs-final from field_value_versions) and the W7 back-fill equality check against pilot_metric_snapshots are not built yet. Gates and tests run once at the S51 end pass (build first, test last).
