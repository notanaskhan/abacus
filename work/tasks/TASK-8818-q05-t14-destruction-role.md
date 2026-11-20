---
id: TASK-8818
title: "Q-05-T14: Destruction role (OQ-1 accepted in ADR-179)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q05t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T14
---

## Objective
On staging a delete of an object with unexpired retention or legal hold on fails under the role, an expired unheld object deletes, and an out-of-batch assumption pages on-call.

## Done
- infra/modules/destruction-role: abacus-<env>-destruction, trust = worker task role with a destruction_batch session tag, allow DeleteObjectVersion (+ retention/hold reads) on the evidence bucket and its replica (variable), explicit deny of BypassGovernanceRetention, PutObjectLegalHold, PutObjectRetention and lock changes; EventBridge rule on an untagged AssumeRole to the on-call SNS topic
- infra/landing-zone/scp-evidence-destruction.json (only the destruction role deletes evidence versions; nobody bypasses governance)
- staging wiring off by default (destruction_role_enabled)
- RB-100 staging proof runbook
- infra/tests/test_destruction_role.py

## Progress log
- `2026-11-20` — Human remainder (DEC-5802): terraform apply, the SCP attachment and the RB-100 staging proof need a person with staging AWS access. Production wiring waits for production compute (no evidence module there yet).
