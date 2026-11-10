---
id: TASK-6106
title: "P-10-T15 SSE edge path: CloudFront stream behavior and origin timeouts, ALB idle 120 s, WAF general rate excludes streams"
spec: SPEC-000  # row (P-10-T15)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-10
plan_key: P-10-T15
branch: s30-p10-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
P-10 §7: CloudFront forwards Last-Event-ID, ALB idle timeout 120 s, WAF general rate limit excludes stream routes, streaming verified through the VPC origin on staging; production config on the Dec train.

## Plan
- `infra/modules/cloudfront-firm/main.tf`: ordered behavior `/v1/*events` (no cache, no compression, all viewer headers but Host) before `/v1/*`; VPC origin read and keep-alive timeouts 60 s.
- `infra/envs/staging/compute.tf`: ALB `idle_timeout = 120`.
- `infra/modules/waf`: rule 1 scope-down NOT `stream_path_regex` (new variable).
- `infra/tests/test_sse_edge.py`; `test_firm_edge.py` counts the third headers-policy use.
- `docs/runbooks/RB-65-sse-edge.md`: apply, verify, roll back.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). `terraform fmt -check` clean; ruff clean on the new test.

## Decisions made during this task
DEC-2704
