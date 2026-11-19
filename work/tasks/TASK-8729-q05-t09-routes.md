---
id: TASK-8729
title: "Q-05-T09: Consultations log v2 routes, create with facts, implementation, release blocker, notifications"
spec: SPEC-711
acceptance_criteria: [AC-11, AC-12, AC-13, AC-14]
risk_zone: amber
status: in-review
branch: s51p-q05-t09-routes
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: Q-05-T09
---

## Objective
Finish Q-05-T09 (TASK-8716): the AUD-28 routes behind audit.consultations_log, the create with facts and consulted role, the conclude with implementation, a reopen that clears the conclusion, positions in the caller's own engagement role, a once-only QM-owner resolution under the engagement's walls, the release snapshot's blocker and the three notifications.

## Plan (amber)
1. assurance/consultations_log_contract.py (GET /v1/consultations, GET/POST /v1/consultations/{id}/…); mounted in assurance api; docs/contracts/completion.md rows; make generate.
2. consultations.py: raise with facts (sealed) and consulted_role; conclude with implemented + reference (400 without a reference); events ConsultationRequested / ConsultationConcluded.
3. consultations_log.py: reopen clears conclusion and implementation (0644's CHECK) and audits the prior conclusion's hash; detail (facts, links, positions, resolution with before_release from report_releases); record_position checks the caller holds that role on the engagement; resolve_difference authorises on the engagement (walls), locks, 409 no_difference_to_resolve; ConsultationDifferenceRecorded to quality partners.
4. release.snapshot: flag on adds also_required consultation_differences (unmet while a difference is unresolved); flag off unchanged.
5. Migration 0985: INSERT (facts_sealed, consulted_role) grant and a consulted_role CHECK; registry INSERT_COLUMNS.
6. tests/integration/backfill/test_q05t09_consultations_v2_routes.py.

## Progress log
- `2026-11-19` — Built. Found on main: reopen set status open with the conclusion still present, which 0644's CHECK refuses; fixed. Not built: the finding's agent proposal shared as cited material (0983 has no attachments table; the epic's consultation_attachments is carried with A-06's suggestion link), the AUD-28 seed (Margaret's 2 open + 3 concluded) with the Q-05 seed slice. Gates and tests run once at the S51 end pass (build first, test last).
