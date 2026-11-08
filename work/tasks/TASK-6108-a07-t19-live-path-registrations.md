---
id: TASK-6108
title: "A-07-T19 live-path registrations bundle, inert until the A-07 flags"
spec: SPEC-000  # row (A-07-T19)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: A-07
plan_key: A-07-T19
branch: s30-a07-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-07 §4.10 and §8.1: every live-path registration A-07 needs, merged before the Dec 24, 2027 freeze and inert until A-07-T33's flags: C7 envelope sources, C11 document kinds, decision kinds and the report reviewable, A-01 rail rows and index tags, the export's seal section, C16 notification kinds.

## Plan
- `assurance/a07_registrations.py`: `LIVE` (all False; T33 replaces it with flag checks); sources `rep_letter` (G7, date-as-of-report check) and `governance_letter` (acknowledgement only, DEC-83) whose providers refuse with 404 while off; the `envelope.completed` consumer (no-op while off); C11 kinds `representation_letter`, `governance_letter`, `audit_report` (pdf, docx; no final approves while off); decision kinds `going_concern` (AU-C 570) and `opinion` (AU-C 700/705), EP-reserved, code options, unraisable while off; reviewable `audit_report_version`; rail rows for AUD-18 to AUD-25 that answer None; tags `report_released`, `archived`; export section `archive_seal` (no file while off).
- `assurance/api.py` calls `register()` and merges the subscription.
- `notifications/catalogue.py`: the 15 C16 kinds of A-07 §4.8.
- Test: `tests/unit/assurance/test_a07t19_live_path_inert.py`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean.

## Decisions made during this task
DEC-2706
