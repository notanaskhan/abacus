---
id: TASK-383
title: Plans and tenant entitlements, require_entitlement, no module flags (F-03-T28)
spec: SPEC-024
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: F-03
plan_key: F-03-T28
branch: f03-t28-entitlements
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"A route guarded by require_entitlement('attest') answers 403 for a firm without it, and no ff.*
module name remains in the flag registry." (ADR-148, P-28; DEC-55)

## What changed
- Migration 0088: `plans` (global, no app privileges) and `tenant_entitlements` (per firm and
  module: attest, internal_audit, group_audit, statements_studio, office_addins, insights; seats,
  agent-minute allowance, validity); the app reads under RLS and writes nothing (operator console
  G-04 and the scenario loader set them).
- `platform.entitlements`: `entitlement()`, `check_entitlement()`, `require_entitlement(module)`
  (a FastAPI dependency); `EntitlementRequired` (403 `entitlement_required`, facts `module`) via
  the new `kernel.errors.DomainForbidden` and its handler.
- The flag registry refuses `ff.*` names and names whose area is an entitlement module.
- Tests: unit (guarded probe route 403/200, registry refusal, registry clean), Postgres
  (in-date row, other firm's row unread, off and lapsed, no app writes).

## Progress log
- 2026-10-22: built. Tests run in the batch's end-of-run CI.
