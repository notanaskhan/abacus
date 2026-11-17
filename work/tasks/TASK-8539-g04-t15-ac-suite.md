---
id: TASK-8539
title: "G-04-T15: ADR-078 AC suite for plan, usage and plan requests"
spec: SPEC-000
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: g04-t15-t16-ac-suites
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T15
---

## Objective
ADR-078 AC suite for AY's amber work: plan read model and seat counts, alert settings and crossings once per period, recipients, plan-request partner gate, billing-rate fake refused outside synthetic firms. AC: files headed ac-test-author notanaskhan pass on main and fail if an alert fires twice in a usage month or a requester approves their own plan request.

## Plan (amber)
1. tests/unit/platform/test_g04t15_independent.py (ac-test-author: notanaskhan): tiles 404 of 490 with the sandbox excluded; rule minutes; crossings lowest first; engagement crossing; the 0920 once-per-usage-month unique index; usage month anchor; allowed() never lets a requester approve; billing rates fake only for synthetic firms

## Progress log
- `2026-11-17` — Built in this session for the notanaskhan row (solo build, written from the spec); 10 pass under xdist (tests/unit/platform shadows stdlib platform when run with -p no:xdist, as the existing platform tests do). Alert settings MFA (budget_alert.manage mfa_recent) runs with the integration suite at the end pass. Gates and tests run once at the S49 end pass (build first, test last).
