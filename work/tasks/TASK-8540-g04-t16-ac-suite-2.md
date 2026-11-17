---
id: TASK-8540
title: "G-04-T16: ADR-078 AC suite 2 for the console and support"
spec: SPEC-000
acceptance_criteria: []
risk_zone: red
status: in-review
branch: g04-t15-t16-ac-suites
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T16
---

## Objective
ADR-078 AC suite 2 for N's console and support work: staff-only routes, metadata-only payload lint, dual audit, provisioning region refusal, two-person publish, no agent tool reads support messages. AC: files headed ac-test-author ayushkbhatia pass and fail if a firm token reaches a platform route or a console payload contains a client name.

## Plan (red)
1. tests/security/test_g04t16_console_isolation.py (ac-test-author: ayushkbhatia): every platform_* action denies firm, portal, agent and system; the console router serves /v1/platform only; content publish and read are platform_admin only; no console Out model carries confidential or restricted data or a client field (the support chat Queue* models excepted, SHL-05); reason fingerprint; region_not_live and approver_is_drafter codes; no agent tool named for support, platform or console

## Progress log
- `2026-11-17` — Built; 49 pass. Lives under tests/security: importing the agents catalogue from tests/unit/platform trips the stdlib platform shadow. Provisioning idempotency, status merge and chat isolation across tenants are DB paths for the end pass's integration run. Gates and tests run once at the S49 end pass (build first, test last).
