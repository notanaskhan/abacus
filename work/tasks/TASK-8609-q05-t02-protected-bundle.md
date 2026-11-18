---
id: TASK-8609
title: "Q-05-T02: Protected bundle: matrix, three conditions, four flags, status rows, glossary, error codes, kinds"
spec: SPEC-711
acceptance_criteria: [AC-29, AC-30]
risk_zone: red
status: in-review
branch: q05-t02-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: Q-05-T02
---

## Objective
Spec section: docs/plan/epics/Q-05.md §4.3, §4.8, §4.10. Matrix rows for quality.*, inspection.*, qm_finding.*, consultation.* (v2), post_issuance.*, retention.* and destruction.*; conditions; archived_exempt post_issuance; four flags; DF-31 status rows; glossary; fresh-MFA list; error codes; C16 kinds.

## Plan (red)
1. Conditions consulted_person, distinct_approver_role, monitoring_reviewer in identity/authz (matrix parse, Rule, ConditionFacts, TargetFacts, has_conditions so none fails open, the security-test harness denies them); inspection_grant waits on the inspection_access_grants table (Q-05-T16, S52).
2. 20 matrix actions: practice (quality, inspection, qm_finding), assurance (consultation v2, post_issuance with archived_exempt post_issuance), evidence (retention, destruction with distinct_approver_role); the agent denied every one. A-06's consultation.conclude is not tightened in the window (P-29): that live-path change rides the Oct 24 train.
3. Flags quality.management, audit.consultations_log, audit.post_issuance, records.governance (default off, expires 2027-05-17).
4. Status objects post_issuance_case, inspection, qm_finding, annual_evaluation, destruction_batch; glossary section; fresh-MFA for six actions.
5. Error modules practice/quality_errors.py, assurance/quality_log_errors.py, evidence/destruction_errors.py; error-codes.yaml rebuilt. The 410 destroyed class arrives with Q-05-T15.
6. Twelve C16 kinds with catalogue events and templates. Rollback: revert (no data).

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5609). Not in the bundle: ARCHIVE-001 and DECISION-001 allowlist entries, archive_guard exemptions and protected-path additions name files that do not exist yet (post_issuance.py, destruction.py); they land with those files (Q-05-T12, T15). Gates and tests run once at the S50 end pass (build first, test last).
