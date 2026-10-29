---
id: TASK-1806
title: Independent AC tests for R-01-T19, T23, T24 (R-01-T30)
spec: SPEC-345
acceptance_criteria: [AC-6]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T30
branch: s13r-r01-t30
created: 2026-10-28
updated: 2026-10-28
---

## Objective
ADR-078 suite for N's red template and policy work: renderer determinism, version immutability, lint with seeded violations (identifier-only refusals), test send to self only, fail closed without a published version, policy cadence, weekend moves, maximum, override and the limit day; the new template, settings and sending-domain actions denied to agent, system and support.

## Plan
- `backend/tests/integration/backfill/test_r01t30_templates_independent.py`
- `backend/tests/unit/communications/test_r01t30_policy_rules_independent.py`
- `backend/tests/security/test_r01t30_template_actions_never.py` (the plan's "test_agent_never.py" does not exist; I-AGENT-NEVER lives in the matrix harness)
- **Gap:** R-01-T27 (DKIM transitions, client-mail gate, suppression) is not built (blocked on the `types-boto3` sesv2 allowlist); its rows wait for it.

## Progress log
- 2026-10-28: written; unit and security files run (22 passed); the integration file runs in the end-of-batch pass.
