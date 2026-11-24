---
id: TASK-8934
title: "Q-05-T24: AUD-30 Post-issuance a-f; AUD-23 g live"
spec: SPEC-711
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-q05t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: Q-05-T24
---

## Objective
AUD-30 Post-issuance (T2 with the Decision dock) at /audits/$auditId/post-issuance, artboards a-f; AUD-23 g switched from fixture to live. Acceptance: AUD-30a to f match at Tier C, no alarm styling appears for the below-CT difference, and Reopen for reissue lands on AUD-23 g with the dual date.

## Done
- Additive reads: case source_name, raised_by_name, opened_at, report_released_at, decided_by_name, rationale; analysis run_number (agents run_numbers); addition post_issuance_case_id; report version dual_date, reissue_of_release_id
- Decide logs a pending archive addition atomically for a case with a source (archive_additions prepare/insert split), linked to the case; optional addition_description
- Omitted procedure decidable without a comparison (two code options); decide guard status <> decided; archive_locked_at reads locked_at of a locked archive only
- Server-registered Post-issuance overview rail row (post_issuance.read, flag, locked archive); cockpit opens AUD-30
- Reissue href is the cockpit's auditors_report section; AUD-23 LiveReport shows Reissued report and the dual date
- Python slice exports scenario.aud30.json; scenarios a-f; screen AUD-30; route behind audit.post_issuance; manifest fixture; e2e spec
- Tests: AUD-30 15, AUD-23 live +2, backend q05t24 6, provider/registry tests extended

## Progress log
- `2026-11-23` — 2026-11-23: built in the S53 sequential run. Red paths touched (post_issuance.py, archive_additions.py): end-pass security review. Assurance unit tests pass (1155); web targeted tests pass (167). Integration/e2e in the end pass.

## Plan
- Files: assurance/post_issuance.py, post_issuance_contract.py, archive_additions.py, providers.py, report_builder.py, release_contract.py; agents/engagement_runs.py + api; evidence/retention_anchor.py + api; quality_slice + fixture_export; web AUD-30 screen, scenarios, seed, route, manifest; AUD-23 LiveReport; packages/ui record-header (audit stateTone).
- Migrations: none (archive_additions.post_issuance_event_id exists since 0669).
- Registry: overview section post_issuance (A-01 registry). No new flags, actions or audit kinds.
- Tests: unit (q05t24, providers, refusals), web (AUD-30, AUD-23 live); integration of decide-with-addition in the end pass.
- Rollback: revert the PR; no schema change.
