---
id: SPEC-306
title: "Sprint 1 data model (F-03): work items, status codegen, the engagement lifecycle, binders and request status v2"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-014, ADR-138]
related_specs: [SPEC-008, SPEC-020, SPEC-027]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
This spec covers the plan's Sprint 1 migrations, taken in its merge order. The plan of record is `docs/plan/epics/F-03.md` §3.1–3.3 and §4.2; this spec carries its acceptance into the repo.

The plan's migration numbers 0056–0059 were already taken on main, so these are 0068 onward.

## 2. Acceptance criteria
- **AC-1 (T05, migration 0068).** Work items:
  - every engagement holds exactly one `assurance` work item and one `primary` engagement_entities row, after the backfill and for every new engagement;
  - a second assurance item is refused;
  - RLS is forced;
  - up/down/up passes.
- **AC-2 (T09).** Status codes are generated from `docs/product/status-vocabulary.yaml`: kernel StrEnums and CHECK strings, plus the `packages/ui` status data. A stale generated file fails `make check-fast`.
- **AC-3 (T12).** The engagement lifecycle:
  - the 14-type CHECK, with `audit` rewritten to `fs_audit`;
  - `single_audit` and `yellow_book` are absent;
  - `service_line`, `office_id` and `standards_set_id` are added;
  - status takes the registry's 8 lifecycle codes, and existing engagements read `active` or `archived`;
  - `gate_policy_overrides` may only tighten a gate.
- **AC-4 (T14).** Binders:
  - `request_lists` gain `work_item_id` (backfilled), `name`, `kind`, `part`, `status` and the published and marked-done stamps;
  - a work item can hold a second binder (part 2);
  - `request_categories` are backfilled from `audit_area`.
- **AC-5 (T11, T15).** Request status v2, per chapter 09 §9.5.6:
  - `open` becomes `draft` when not client-visible, otherwise `requested`;
  - `received` and `ready_for_review` become `uploaded`;
  - `needs_revision` becomes `returned`;
  - `accepted` becomes `received`;
  - `not_applicable` is added;
  - overdue is never stored;
  - a banned pattern rejects the old literals.

## 3. Out of scope
- Module registries and pre-registration (T07, T08).
- The C1 work-item routes beyond reads, and the contract-test CI (T18, T19).
- The `reminders` rename (T16, Sprint 2).
