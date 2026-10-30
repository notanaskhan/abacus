---
id: TASK-2307
title: T-01-T16 consent registry read API and lifecycle
spec: SPEC-501
acceptance_criteria: [AC-39, AC-40, AC-41, AC-42, AC-43, AC-44]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T16
branch: s18-t01-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
GET /v1/consents with tiles, needs-attention sort, filters, walls with no hidden count and
offshore filtering; detail with document, signers, method and agent reads since signature;
summary; ConsentExportWorkflow (CSV, audited, fresh MFA); ConsentLifecycleSweep schedule
(Expiring at 30 days, consent_expiring notification, register-drift re-consent flag) with a
replay history. Acceptance (row): the registry returns 218 with tiles 212, 2, 1, 1, 1, 1 at Sep
14, 2026, Rao shows Expiring 16 days, and a walled user sees neither the row nor a count.

## Plan (red: written before the build)
- Stacked on #820 (T-01-T10).
- `organisations/consent_registry.py` (reads, export, sweep), `workflows.py`, `activities.py`;
  routes in `consents_contract.py`; WORKFLOWS/ACTIVITIES/SCHEDULES in `organisations.api`.
- Migration 0463: consent event kinds `expiring`, `reconsent_required`.
- Notifications: `consent.expiring` kind and template. Kernel: `consent-register` bundle kind.
- Tests: `tests/unit/organisations/test_t01t16_consent_registry.py`; the seeded 218/tiles figures
  need T-01-T23's scenario slice; replay histories at the end review.
- Rollback: revert; 0463 downgrade restores the kinds.

## Progress log
- `2026-10-30` — built (DEC-1354). Tests written, not yet run (S18 end review; `[skip ci]`).

## Handoff
- **Current state:** built, PR open, held for the S18 batch (after #816, #818, #819, #820).
- **Exact next step:** K-02 workstream (K-02-T06).
