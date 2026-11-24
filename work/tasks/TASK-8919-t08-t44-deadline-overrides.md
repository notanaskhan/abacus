---
id: TASK-8919
title: "T-08-T44: DF-10 firm deadline overrides and client relief applications"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t08t44
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T44
---

## Objective
Row: "DF-10 firm overrides handed over by T-03: internal target offsets per form, holiday and postponement lists, and per-client postponement application by notice id on top of the platform rules; firm rows editable and owner-published in KNW-04 section j with platform rows read-only; applied inside practice.api.due_dates_for with version pinning." Acceptance: "Firm override rows are versioned and owner-published, platform rows stay read-only, and a postponement applied by notice id moves only that client's dates on HOME-03."

## Done
- migration 1016_deadline_overrides: firm_standards kind deadline_overrides; postponement_applications (insert-only, human-only)
- methodology: DeadlineOverridesPayload (offsets, closures, postponements), deadline_overrides_in_effect, KNW-04 section j read GET /v1/standards/deadline-rules
- practice/deadline_overrides.py: internal targets, notice window logic, applications, apply_postponement (human, fresh MFA, idempotent), apply_overrides
- practice recompute applies overrides (internal_target_on, client relief, pins); detail answers internal_target_on; due_dates_for(..., tenant_id, client_id) with pins
- POST /v1/postponement-applications live; notice_id a string
- registries restructured (closes, engagements, methodology, workpapers) for pyright
- tests: unit 6 pass; integration test for the end pass; DEC-5921

## Progress log
- `2026-11-23` — Built in full. End pass: make generate (new route, contract changes), integration tests.
