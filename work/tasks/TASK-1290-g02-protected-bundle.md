---
id: TASK-1290
title: G-02 protected bundle - matrix rows, four flags, DF-31 statuses, glossary, error codes, notification kinds, audit slots
spec: SPEC-349
acceptance_criteria: [AC-45, AC-46]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T02
branch: s9c-governance
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The protected bundle every later G-02 task builds on (G-02 §4.10): registry and protected-file
edits only, no routes and no migration.

## Plan
- **Matrix** (`docs/architecture/permission-matrix/`): `audit_trail` (`audit_event.read` + 
  `security_admin`, `practice_leader: in_scope`, agent and system denied; `audit_event.export`),
  `identity` (`security.read`, `security.manage`, `session.end`, `staff.unlock`;
  `support_session.read/manage` and `firm_agents.pause` widened), `agents` (`ai_policy.read`,
  `.draft`, `.publish`, `.approve`), `evidence` (`firm_export.schedule`), `platform`
  (`incident.read`, `incident.decide`). `level_in(partner)` is written `firm_partner` (DEC-132).
  Every new write denies `agent` and `system`. `make regenerate`, never a hand edit.
- **Fresh MFA register**: the eight governance writes; group `incident` added to the lint and its
  test (the register already said G-02's `incident.decide` joins it).
- **Flags**: `audit_log.explorer`, `audit_log.values` (new `feature-flags/audit_trail.yaml`),
  `security_center.v1` (identity), `ai_policy.v1` (agents); off, owner notanaskhan, DEC-137
  override as the other stubs.
- **DF-31 statuses**: `ai_policy_version`, `security_incident`, `firm_export`, `support_session`;
  pills null until the screen contracts (T03). Staff sign-in "Locked" is `invitation.locked`.
- **Glossary**: security policy, SSO-exempt account, audit request context, audit event label.
- **MODULE_DEPENDENCIES**: `audit_trail → platform`.
- **Error codes** (classes declared, raised later): `sso_not_verified`, `support_requests_disabled`,
  `superseded_by_ai_policy`, `policy_loosening_refused` (identity, agents), `approver_must_differ`
  (agents), `decider_must_differ` (platform). `values_withheld` is a values-section status, not
  an error code (SPEC-349 §8).
- **Notification kinds**: six new C16 kinds (`firm_export_*` already registered by Q-02).
- **Slots**: `platform.audit_slots` (labeler, value resolver; fail closed; Restricted labels
  refused).
- **Not done here:** `TABLE_OWNERS` (no new table in this bundle: T10, T14, T19, T20, T23 add
  theirs); the human-only audit-action register (`docs/architecture/human-only-actions.yaml`) is
  being changed by three other branches, so G-02's human-only audit actions (`ai_policy.approved`,
  `incident.decided`, `firm_export.schedule_approved`, ...) are added with the tasks that write
  them, after those branches merge. The matrix rows already deny agent and system.
- **Approval:** under the solo amendment the approval file is DEC-416.
- **Tests:** `tests/unit/governance/test_g02_protected_bundle.py`; the generated matrix and
  fresh-MFA suites.
- **Rollback:** revert; nothing reads the new rows or flags yet.

## Progress log
- 2026-10-26: built; regenerated; generated security suites, notification and quality tests green.
