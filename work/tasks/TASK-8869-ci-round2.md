---
id: TASK-8869
title: "S52: CI round 2: hangs, hidden failures and recorded timings"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: shard-round2
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: S52
---

## Objective
Tip CI on 52a135ea7 (run 44923971725): seven integration shards hung until the 100-minute cancel, unit shard 3 was cut at 45, and tests that had sat in never-finished shards now ran and failed. Fix them in code or fixtures without weakening a test, and merge the recorded timings.

## Done
- durations.json: merged from the run's 23 recorder artifacts (shard --record-runs --partial): 1,491 files, 21.8 worker-hours; integration now balances to about 59 worker-minutes a shard
- Hang guard: ci-integration runs pytest with faulthandler_timeout=1500 and faulthandler_exit_on_timeout, so a test past 25 minutes dumps every stack and its worker is replaced (checked: the hung test fails, the rest pass)
- Seven tests each ran the full banned_patterns.scan() (up to 27 minutes each under CI branch coverage) to filter one rule: they share a session fixture real_banned_scan (tests/conftest.py) in xdist_group banned-patterns-real-scan
- SECURITY BUG (Q-05-T16, S52): inspection_grants.sweep opened a unit of work with nothing to revoke and raised MissingAuditEvent; sweep_firm runs it first, so the hourly access-end pass failed for every firm and no seasonal access ended. It now checks read-only first
- Support sessions: starts_at and expires_at come from one clock read (the window is exactly the duration; g04t07 AC-20)
- test_permission_matrix ac20 depended on another test having imported engagements.api (it registers the client-wide grant scopes): the test imports it
- C-01-T17 ledger-sync stub gains capabilities() (C-02-T26 reads it)
- test_s38: 0961 (T-08-T06, DEC-5605) widened planning_opportunities.status to six; the test asserts the exact six
- P-08-T22 T14: the synthetic firm's names left product constants: PLT-01 tenant rows moved to abacus_tools.synthetic.g04_tenants, the seed's audit reason and two OpenAPI examples made neutral (make generate)
- A-03-T16: make fixtures SNAPSHOT=2026-09-24T10:20 adds the three MUS fields to two exports

## Progress log
- `2026-11-22` — Local: the 6 touched integration files 96 passed; unit shards as CI splits them pass apart from this laptop's WeasyPrint library; banned_patterns, ruff, pyright clean. DEC-5866.
