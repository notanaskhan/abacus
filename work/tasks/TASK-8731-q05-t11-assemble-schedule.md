---
id: TASK-8731
title: "Q-05-T11: Destruction assembly on the platform schedule, S3 retain-until observer, unlocked-archive reader"
spec: SPEC-711
acceptance_criteria: [AC-21, AC-22]
risk_zone: red
status: in-review
branch: s51p-q05-t11-assemble-schedule
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T11
---

## Objective
Finish Q-05-T11 (TASK-8713): DestructionAssembleWorkflow runs the quarter's assembly on the first business day after the quarter ends, firm by firm behind records.governance, observing each version's S3 retain-until; assurance registers its released-but-unlocked archives so nothing in them is eligible.

## Plan (red)
1. evidence/storage.observed_retain_until: S3's retain-until; only no-lock / no-such-version codes read None (through kernel error_code, STORE-001), any other failure fails that firm's run.
2. evidence/destruction_workflow.py (DestructionAssembleWorkflow, batch class) and destruction_jobs.py (activity, daily Schedule destruction_assemble:platform, first_business_day_after_quarter_end over K-02's legal_holidays in Central time); registered in evidence api.
3. assurance/release_facts.unlocked_archives registered through evidence api's register_unlocked_archives.
4. Replay history destruction-assemble-v1-swept.json (record_s51_destruction) and its replay test; unit tests for the quarter-day rule and the registration.

## Progress log
- `2026-11-19` — Built. The sweep is daily and acts only on the quarter's first business day; assemble() is once per quarter ref, so a retried day never makes a second batch. Not built: the FIL-02 1,204 / 31 figure needs the Q-05 seed slice's former-client documents. Gates and tests run once at the S51 end pass (build first, test last).
