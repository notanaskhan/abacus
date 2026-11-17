---
id: TASK-8536
title: "C-01-T47: Independent AC tests for the closes services"
spec: SPEC-655
acceptance_criteria: [AC-37, AC-42, AC-48, AC-49]
risk_zone: amber
status: in-review
branch: c01-t47-t49-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T47
---

## Objective
ADR-078 independent AC tests for accounts, reconciliation, issues, flux and registrations from SPEC-655 F5-F9: staleness by hash; classify_entry holds attest entries; flux both legs; drafted entries balance; portal principals denied.

## Plan (amber)
1. tests/unit/closes/test_c01t47_independent.py: Cedar Mutual schedule 700 a month; tie, ties once posted, off by the cent; inputs hash staleness (schedules, flux); flux both legs and not comparable; classify_entry attest always held, prepaid limit inclusive, unlisted review; entry_lines for the 380 refund; close tools read/compute/propose; portal and support denied on every close action

## Progress log
- `2026-11-17` — Built in this session for the notanaskhan row (solo build; written from the spec and handoff figures). 18 pass. The DB-backed cases (L1 blocked while items are open, portal scope isolation INV-4, identifiers-only notifications) run at the end pass with the integration suite. Gates and tests run once at the S49 end pass (build first, test last).
