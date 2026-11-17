---
id: TASK-8405
title: "A-08-T34: ADR-078 independent AC tests for T15 and T19 and the confirmation isolation suite"
spec: SPEC-657
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
branch: a08-t34-confirmation-isolation
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T34
---

## Objective
Spec section: docs/plan/epics/A-08.md §3 F7 (I-CONFIRMATION-ISOLATION). ADR-078 independent AC tests for T15 and T19 plus backend/tests/security/test_confirmation_isolation.py: no enumeration, OTP lockout, single answer, expiry, other confirmations unreachable, client token 404, hostile attachments, kill switch.

## Plan (red)
1. `backend/tests/security/test_confirmation_isolation.py`, written from SPEC-657 AC-7.x and the confirmations contract (not the implementation): eight properties against the HTTP surface and the link principal, with `_indistinguishable` as the one judgement and two planted-difference tests proving it fails on a leaking build.
2. Seeds through the security suite's Seeder: a firm, Granite Peak, an engagement, confirmations created by the service, set Sent, links minted for `confirmation`; codes issued through `issue_link_code` as communications does.

## Progress log
- `2026-11-17` — Written in the S48 sequential stack; ruff and pyright clean; not run (the end pass runs the security directory). The hostile-attachment check accepts the scanner's refusal code (`file_refused`/`file_type_refused`), whichever the fake scanner raises for EICAR with an executable name. Gates and tests run once at the S48 end pass (build first, test last).
