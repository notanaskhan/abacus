---
id: TASK-6233
title: A-05-T58 remainder, Schedule H line 4i's description column and its C11 render
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T58
branch: s31d-a05-t58-4i
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-09
updated: 2026-11-09
---

## Plan (amber)
- Migration 0744 on 0743 (expand-only): `ebp_trust_report_lines.description`,
  `ebp_participant_loans.interest_rate`, INSERT grants. Rollback: revoke and drop.
- Migration 0745 on 0744 (expand-only): `generated_documents.kind` and `report_templates.family`
  CHECKs gain `ebp_supplemental_schedule`. Rollback: the old lists, `NOT VALID`.
- `compute.ebp.form5500.loans_description`; `schedule_4i_facts` reads the stored description and
  the loans' rates and latest maturity.
- `assurance.ebp_schedule_render`: the composed kind, `compose_4i`, `render_4i` (person only).
- Contract (additive): `POST /v1/audits/{work_item_id}/ebp/form-5500/schedules/4i/render`
  (`ebp_schedule.render`, 201); EBP-07's `allowed_actions` names it; C11's kind literal widens.
- EBP-07 fixture: column (c) from the handoff.
- Tests: `test_a05t58_schedule_render.py` (unit), `test_a05t58_4i_render_migration.py`
  (integration), the stub contract's route set, `EBP-07.test.tsx`.

## Left
- Nothing writes trust report lines or loans in live mode yet (A-05-T39's extraction); column (c)
  fills when they do.

## Progress log
- 2026-11-09: built; tests run at the end pass.
