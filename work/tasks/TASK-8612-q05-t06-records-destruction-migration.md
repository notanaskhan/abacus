---
id: TASK-8612
title: "Q-05-T06: Migration 0964 records_destruction in evidence"
spec: SPEC-711
acceptance_criteria: [AC-31, AC-32, AC-22, AC-25, AC-27]
risk_zone: red
status: in-review
branch: q05-t06-records-destruction-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: Q-05-T06
---

## Objective
Spec section: docs/plan/epics/Q-05.md §4.2 NNNN_records_destruction. Extend Q-02's tables (policy text and effective date on versions; hold display name, classes, until_released and two reason codes), destruction batches, items, exclusions, approvals and certificates, evidence tombstones and the destruction_execute control.

## Plan (red)
1. migrations/versions/0964_records_destruction.py on 0963: Q-02 columns added (nullable or defaulted), legal_holds reason CHECK widened additively; five new evidence tables with forced RLS, four insert-only; destruction_batches forward-only status trigger; destruction_approvals human-only, UNIQUE per person and per role, a trigger capping two and requiring the phrase hash on the second.
2. evidence_versions: destroyed_at and destruction_certificate_id; evidence_versions_immutable replaced to allow exactly the one NULL-to-value tombstone write under app.archived_write = destruction_tombstone (every other column unchanged), restored on downgrade.
3. platform_controls and platform_control_changes CHECKs accept destruction_execute; kernel/controls.ControlName and the operator CLI know it.
4. evidence/registry.py, schema_check entries. Rollback: downgrade restores Q-02's CHECKs, the original immutability function and drops the new columns and tables.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5612). Q-02's policy versions are written by its trigger, so the app gets no insert grant on the new columns; the trigger change is live-path and rides Q-05-T11 after Oct 24. T14/T15 (version deletion) wait on the P-14 amendment (Q-05-T32). Gates and tests run once at the S50 end pass (build first, test last).
