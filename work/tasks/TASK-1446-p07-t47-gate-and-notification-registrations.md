---
id: TASK-1446
title: Human-gate and notification registrations (P-07-T47): C13 gate kinds and C16 kinds and database templates for acceptance, risk review, independence reminders, team approval and invitation expiry
spec: SPEC-332
acceptance_criteria: [P-07-T47]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T47
branch: s11-engagements
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Daniel Reyes's HOME-02 row appears once Thornbury is sent to the partner and disappears when the
decision is recorded."

## Plan
- **Gates (C13, DEC-539):** `engagements/human_gates.py` computes the four gate kinds from
  engagements' own records; `review/engagement_gates.py` registers them through the existing
  `register_gate_source` (review already depends on engagements). `review/gates.py` C13_EVENTS
  gains the engagement events the sources name. No I-01/HOME module code is touched.
- **Events (identifiers only):** `independence.reminded` (replaces the reminder's second
  `independence.requested`), `independence.conclusion_due`, `acceptance.review_requested`,
  `team.change_proposed`, `eqr.eligibility_approved` in `engagements/events.py`, emitted in the
  existing units of work beside their audit events.
- **Kinds (C16, DEC-540):** six registrations in `notifications/catalogue.py`, five with catalogue
  entries and fixed in-app sentences; `invitation_expiring` registered without a producer.
- **Templates:** content, through the staff import (`notification.<kind>`), never code or seed.
- No migration, no matrix row, no flag.
- **Tests:** `tests/integration/backfill/test_p07t47_engagement_gates.py` (the acceptance line,
  registrations, the risk-review recipient); `test_catalogue.py` and `test_team_roles.py` updated
  for the new events.
- **Rollback:** revert the commit; projected rows of the four kinds stay as `open`/`done` rows a
  rebuild no longer produces (`rebuild_human_gates` leaves unknown sources' rows alone).

## Progress log
- 2026-10-27: built and registered; DEC-539, DEC-540. The I-01 lane's `subkind` (I-01-T04) should
  map these subject types to its column when it lands.
