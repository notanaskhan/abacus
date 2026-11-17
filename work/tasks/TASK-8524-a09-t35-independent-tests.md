---
id: TASK-8524
title: "A-09-T35: Independent AC tests for group scoping and the POR-23 room"
spec: SPEC-658
acceptance_criteria: [AC-5, AC-6]
risk_zone: amber
status: in-review
branch: a09-t35-independent-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T35
---

## Objective
Spec section: docs/plan/epics/A-09.md §3 F5, F6. Independent AC tests (ADR-078) for AY's amber code and UI: scoping goldens (240,000, 180,000, 12,000; 192,000, 144,000, 9,600; component PMs; coverage), POR-23 read-model allowlist and client words, component_thread share guard; fails on a component auditor reading the consolidated TB and on Late rendering in the room.

## Plan (amber)
1. `backend/tests/unit/assurance/test_a09t35_independent.py` (14 tests, ac-test-author notanaskhan): the goldens; component PM defaults (135,000 / 108,000 / 90,000 / 72,000 off group PM 180,000) and the refusal at or above group PM; coverage; the Room and RoomDeliverable fields as an allowlist with no figure; ClientWord never a firm word (no Late); a component scope carries no engagement (so no engagement-wide resource passes scope_only); the share guard.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack. 14 passed (run once). The reserved-role decide and 'no browser arithmetic' checks need the AUD-34 card and web tests; they run with A-09-T38's live swap in the end pass. Gates and tests run once at the S49 end pass (build first, test last).
