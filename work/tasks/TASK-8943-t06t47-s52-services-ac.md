---
id: TASK-8943
title: "T-06-T47: Independent AC tests for AY's S52 entity-return services"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t06t47
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-06-T47
---

## Objective
Independent AC tests (ADR-078) for AY's S52 services: fixed assets, book-tax, basis and section 754, states and PTET, hand-off landing; human-only approvals, seen_version 409s, issue dedupe, DEC-88 visibility, consent refusals, TRI absent from logs.

## Done
- tests/integration/backfill/test_t06t47_s52_services_ac.py (4): another firm 404 on fixed-assets/basis/states/handoff; client principal refused; off-engagement person refused (DEC-88); a return with no hand-off has an empty landing

## Progress log
- `2026-11-23` — 2026-11-23: written from T-06 §3 F1-F4, F6; integration run in the end pass. Figure-level, seen_version, issue-dedupe and consent ACs are held by the T-06 service suites (t06t33-t06t39); the end-pass review checks each named.
