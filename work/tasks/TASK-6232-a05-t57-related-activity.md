---
id: TASK-6232
title: A-05-T57 remainder, AUD-27's related-party transactions and disclosure
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T57
branch: s31d-a05-t57
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-09
updated: 2026-11-09
---

## Plan (amber)
- Migration 0743 on 0742 (expand-only): `related_parties.transactions` (jsonb array, default `[]`),
  `disclosure` (text) and `disclosure_note` (bool; a note link needs the words), with the app
  role's INSERT and UPDATE on the three. Rollback: the downgrade revokes and drops them.
- `aud27.PartyRecord`, `record_activity` (human-only, `related_party.manage`, audited
  `related_party.activity_recorded`); the read returns the three and the screen-out reason.
- Contract (additive): `PUT /v1/audits/{work_item_id}/related-parties/{party_id}/activity`
  (`RelatedPartyActivityIn`); `Aud27ItemOut` gains `disclosure`, `disclosure_note`,
  `screened_out_reason`; create passes the relationship.
- AUD-27 b: the "FY2026 transactions" and "Disclosure" columns; fixture rows from the handoff.
- Tests: `test_a05t57_related_activity.py` (unit), `test_a05t57_related_activity_migration.py`
  (integration), the stub contract's route set, the schema grant contract, `AUD-27.test.tsx`.

## Left
- The footer's "Citations (n)" and "Procedures (n)" (DV-AUD-27-4): nothing anchors a citation or
  a program step to an estimate (DEC-2827).

## Progress log
- 2026-11-09: built; tests run at the end pass.
