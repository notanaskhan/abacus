---
id: TASK-1330
title: Read-time value resolution for the audit log (G-02-T09)
spec: SPEC-349
acceptance_criteria: [AC-5, AC-10, AC-11]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T09
branch: s10b-audit-read-service
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The detail's `values` section, resolved per viewer at read time (DEC-60, ADR-024): `withheld`
`not_enabled` with `audit_log.values` off, `withheld` `need_to_know` for metadata-only readers,
`resolved` or `unavailable` (fail closed) for a viewer with the target's content read; a
Restricted value only ever masked; nothing stored.

## Plan
- `platform/audit_slots.py`: value rows gain `item_label`, `amount` and `classification`;
  `audit_values` masks any Restricted row the resolver left unmasked (last four kept) and refuses
  an amount that is not a decimal string; a `register_audit_source` slot (fails closed to none)
  for the Source section, which agents registers when its run read lands.
- `audit_trail/values.py`: who may see values (engagement events: `engagement.read` on the
  engagement; firm-level events: the QM owner); `firm_admin`/`security_admin` never.
- Resolvers in `platform/audit_resolvers.py` for identity-owned types the platform may read
  (`ethical_wall`; labeler for `user`); the other v1 types register as their owners land.

## Tests
`tests/unit/platform/test_audit_values_masking.py`, AC-5 and AC-10 in suite 1, T08's file.

## Rollback
Flag `audit_log.values` off: every values section reads `withheld` `not_enabled`.

## Progress log
- 2026-10-26: built with T08, T10. Masking enforced in `platform.audit_values`; `user` labeler
  and `ethical_wall` resolver registered by platform (identity imports no module); firm-level
  values through `audit_event.read_firm_values` (QM owner). Labelers now accept a `None` viewer
  for the label index. Other v1 types (ai_policy, security_policy, support_session, membership,
  evidence_version, request_item, pii_reveal) wait for their owners: partial (DEC-435).
