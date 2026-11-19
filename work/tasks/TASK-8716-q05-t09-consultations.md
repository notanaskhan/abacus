---
id: TASK-8716
title: "Q-05-T09: Consultations log v2 (dark): migration and service"
spec: SPEC-711
acceptance_criteria: [AC-11, AC-12, AC-13, AC-14]
risk_zone: amber
status: in-review
branch: q05-t09-consultations
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T09
---

## Objective
Migration 0983: consultations gains facts, consulted role, implemented and reference, reopened_at; insert-only consultation_links, human-only consultation_positions and consultation_resolutions. assurance/consultations_log.py: firm log over visible() rows with wall-safe counts and filters (engagement, status, consultee, year), reopen, attach (links), record_position, resolve_difference (QM owner) and the release blocker unresolved_differences. Conclude stays A-06's consultee-only.

## Plan (amber)
1. migrations/versions/0983_assurance_consultations_v2.py (on 0982).
2. assurance/registry.py: Q05T09_TABLES, insert columns, consultations' new update columns.
3. assurance/consultations_log.py.
4. tests/integration/test_q05t09_consultations_log.py (DB; end pass).

## Progress log
- `2026-11-19` — Built (service and migration). Not built: the v2 routes and generated client (contract-first under the audit.consultations_log flag), the create with facts and the finding's agent proposal shared as cited material, the release-gate registration of unresolved_differences, and the notifications; the AUD-28 seed (Margaret's 2 open + 3 concluded) is not seeded. Gates and tests run once at the S51 end pass (build first, test last).
