---
id: TASK-1950
title: "P-07-T47 remainder: the day-12 `invitation_expiring` producer"
spec: SPEC-332
acceptance_criteria: [AC-9]
risk_zone: amber
status: in-review
epic: P-07
plan_key: P-07-T47
branch: s11p-p07-t47
worktree: ../abacus-s11p
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Firm admins are told on day 12 of a 14-day client invitation that it is about to lapse
(P-07 §4.8), closing the "registered, no producer" gap left by TASK-1446 (DEC-540).

## Plan
- **Pass:** `identity/invitation_expiry.py`, run by the hourly identity activity
  (`access_end.sweep_access_ends_activity`) after access ends; no new Schedule or workflow, so no
  recorded history (DEC-1000).
- **Migration 0360:** `invitation_expiry_notices` (insert-only, forced RLS), one row per
  invitation and expiry; registered in `identity/registry.py`.
- **Event:** `invitation.expiring` (`InvitationExpiring`, ids only); catalogue entry
  `invitation_expiring` to firm admins, subject `client_invitation`, engagement for walls; audit
  `client_invitation.expiry_notified` (reviewed fallback).
- **Tests:** `tests/integration/test_p07t47_invitation_expiring.py`; `test_catalogue.py` list;
  `make regenerate` for the generated tenant-isolation table list (end review).
- **Rollback:** revert; 0360's downgrade drops the table. Already-sent notifications stay.

## Progress log
- 2026-10-28: built; DEC-1000. Tests written, not yet run (run at the end review, per the S11
  pending build's agreement). Migration 0360 chains on 0291: re-chain if other sessions' 0292+
  or 0320+ land first.
