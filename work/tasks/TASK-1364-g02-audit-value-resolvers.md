---
id: TASK-1364
title: Audit value resolvers for evidence_version, request_item, pii_reveal, membership, support_session (G-02-T09 gap)
spec: SPEC-349
acceptance_criteria: [AC-5, AC-10, AC-11]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T09
branch: s10c-audit
created: 2026-10-27
updated: 2026-10-27
---

## Objective
DEC-435 left five v1 target types reading "Values not available" until their owners register.
Their owners exist: register a resolver for each, classified, Restricted values masked, with the
need-to-know and flag-off paths (`audit_trail/values.py`) unchanged in front of them.
`ai_policy` and `security_policy` stay unavailable until G-02-T14/T15 (S11).

## Plan
Every resolver answers only facts the event pins (its references, or immutable columns of the
target row) and fails closed (`unavailable`) otherwise: never a value that may have changed
since the event. Field names are codes and values are codes, ISO dates, display names, file
names or masked tokens: the SPA words the codes (G-02-T13); no UI copy is invented here. When
the event names an engagement, the target must belong to it, else `unavailable`.
- `evidence_version` (`evidence/audit_values.py`, registered from `evidence/api.py`): item label
  the version's file name (Confidential); `pii.revealed` (the pii_reveal source): the region's
  kind with `mask_token(kind, last4)`, Restricted and masked (the sealed value is never opened);
  review assignment refs (`user_id`) as display names.
- `pii_reveal` (same file): the same answer when an event targets the reveal itself.
- `request_item` (`requests/audit_values.py`, from `requests/api.py`): item label the title
  (Confidential); `client_visible` and `user_id` (client assignee) before and after from refs.
- `membership` (events on `user` targets, `membership.*`; identity depends on no module, so
  `platform/audit_resolvers.py` registers over a new `identity.api.membership_audit_facts`):
  role template from `template`; security role from `security_admin`; deactivation reason
  from `reason`; changed attributes only while the membership still stands at the event's
  `version` (else unavailable).
- `support_session` (identity; platform registers over `identity.api.support_session_audit_facts`):
  `requested`: scope, minutes, emergency, reason (Confidential); approvals: status and window;
  `ended`/`revoked`/`expired`: status.
- DEC-459.

## Tests
`tests/integration/test_g02t09_audit_value_resolvers.py`: per type, a resolved section, every
Restricted row masked (the reveal shows `•••-••-NNNN` only), `withheld` `need_to_know` for a
metadata reader and `not_enabled` with the flag off; a mismatched engagement is unavailable.

## Rollback
Revert: the types read "Values not available" again. Flag `audit_log.values` off withholds all.

## Progress log
- 2026-10-27: built as planned. `pii_reveal`: writers record reveals on the version
  (`pii.revealed`), so the evidence_version resolver answers them; a `pii_reveal` resolver
  gives the same answer for an event on the reveal itself. Membership resolves on `user`
  targets (`membership.*` actions). Index maps exposed as `people.DEACTIVATION_REASONS` and
  `staff.FIRM_ROLES_BY_INDEX`. DEC-459. `test_g02t09_audit_value_resolvers.py` (6 tests) green
  in the targeted pass; gates clean (TYPE-001 caught once on a pyright ignore, fixed with a cast).
- 2026-10-27: security review M1: unscoped evidence and request events (most writers pass no
  `Scope`) read as firm-level, so the QM owner passed need-to-know; the two resolvers now load
  the target's engagement and require `engagement.read` on it (`allowed_actions` probe, as
  `values.may_see_values`), else unavailable. `test_m1_*`: an off-team QM owner gets
  unavailable on both; an on-team quality partner resolves.
