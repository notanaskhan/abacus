---
id: TASK-8810
title: "C-02-T25: Enablement on live paths: firm switch, posting_enabled, client write grants, write log"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-c02t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T25
---

## Objective
Posting is refused until all four switches are on, a revoked grant stops the next entry mid-batch and an attest-flagged client can never hold a write grant.

## Done
- integrations/w1_switches.py: firm switch (security_admin, fresh MFA, 409 write_capability_not_released while unreleased, disable always), ADM-08b gl_posting_settings (0992; memo prefix, Post as; locked rows in code), engagement posting_enabled (attest refused, I-POLICY-NOT-ATTEST), POR-16 grant/revoke (fresh MFA, consent copy v2, attest refused before the DB trigger), client-visible write log via connections.register_access_log_writes
- every W1 route in w1_contract built (no 501 left)
- posting writes carry the memo prefix
- reviewed audit actions
- unit tests test_c02t25_w1_switches.py

## Progress log
- `2026-11-20` — Plan (red): service, migration 0992, routes, log slot, memo; rollback revert + downgrade 0992. Built dark (DEC-5800); the Oct 24 train flips stay human. Security review and DB-backed tests at the end pass.
