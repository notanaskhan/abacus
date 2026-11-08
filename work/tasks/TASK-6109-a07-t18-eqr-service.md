---
id: TASK-6109
title: "A-07-T18 EQR service: open on assignment, digest by code, the EQR's acts, concur (G6), Request EQR\u2026"
spec: SPEC-000  # row (A-07-T18)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: A-07
plan_key: A-07-T18
branch: s30-a07-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-07 §3.1: the EQR review opened on assignment with eligibility re-checked, checklist from the firm template, digest built by code from decided cards, mark reviewed, EQR notes as review notes on the review, concur (assigned EQR only, 10 of 10, notes cleared, attestation, fresh MFA, five-layer human-only), and Request EQR… (DF-05).

## Plan
- `assurance/eqr_service.py`: `open_reviews` (eligibility re-check through `engagements.api.eqr_eligibility`; checklist from `register_eqr_checklist_template`, 409 `eqr_template_missing` without one), `on_eligibility_approved` subscription, `build_digest` (decided EP cards, SHA-256 snapshots, supersede on change), `mark_reviewed`, `update_checklist` (optimistic version), `concur` (403 `eqr_only`, `mfa_required`, 409 `eqr_notes_open`/`checklist_incomplete`, v2 `eqr_concurrences` row, review concurred, `eqr.concurred` audit, `eqr.concurred_v2` event), `request_eqr` (`eqr.requested`).
- `engagements/team.py` + api: `eqr_eligibility(tenant, engagement, user)`.
- `notifications/catalogue.py`: `eqr.concurred_v2` → `eqr_concurred` to the partners; `eqr.requested` → `eqr_requested` to the EQR; test list updated.
- `assurance/api.py`: subscription and export.
- Tests: `tests/unit/assurance/test_a07t18_eqr_service.py`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
DEC-2707
