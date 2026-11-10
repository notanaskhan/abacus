---
id: TASK-6709
title: "P-10-T37: independent AC and security tests for SSE (P-10-T15, T26): tests/security/test_sse_payloads.py"
spec: SPEC-647
acceptance_criteria: [AC-T1, AC-T2]
risk_zone: red
status: in-review
branch: s35-p10-t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T37
---

## Objective
Tests written in ayushkbhatia's session pass and fail if any event carries a Restricted value or a stream outlives a wall change by more than 60 s.

## Plan
`backend/tests/security/test_sse_payloads.py` (ADR-078 solo independence, as DEC-3127/DEC-3201):
written from SPEC-647 §3.8, ADR-232 and the rows' acceptance, not from the implementation's tests.
Payloads (identifier-only checker; ref_only over 64 KB with nothing else; `RunStateChanged`
classification; every `run_events` writer's payload keys), backfill in order, resync on a pruned
cursor, locked on a wake within one loop and on the 60 s re-authorisation without a wake, the
six-stream cap and per-tenant slots, unknown topic kinds refused, the run stream reading under the
caller's tenant and re-authorising.

## Progress log
- `2026-11-10` — Written; run at the end pass. P-10-T15's edge half (CloudFront, ALB idle
  timeout, WAF) is infrastructure verified on staging, not by these tests.
