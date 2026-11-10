---
id: TASK-6570
title: "P-10-T26 portal remainder: portal streams close 30 seconds before the access token expires"
spec: SPEC-647  # P-10 SSE core
acceptance_criteria: [AC-T5]  # close 30 s before token expiry
risk_zone: red
status: in-review
branch: s33t-p10-t26-portal
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T26
---

## Objective
TASK-6541 closed firm-app streams before token expiry; a portal stream still waited for the
60-second re-auth. The portal session lookup now answers the access token's expiry.

## Plan (red)
- Migration 0762 (on 0761): `portal_invitee_resolve(text, text)` dropped and created again with an
  `access_expires_at` column; the same checks (live portal session on its pinned host, every
  expiry ahead), owner and grants (`REVOKE ALL FROM PUBLIC`, `EXECUTE TO abacus_app`). Static SQL
  only. Downgrade restores 0140's shape.
- `identity/portal_session.portal_context`: `note_session(token_expires_at=row.access_expires_at)`
  before returning the person's context; the streams already read it (DEC-3141).
- Test `tests/unit/identity/test_s33t_p10t26_portal_expiry.py`.
Rollback: downgrade 0762, revert.

## Progress log
- `2026-11-10` — Built; unit test passes; migration not applied locally (no database here); CI
  applies it. Gates at the end of the round.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3170 | The portal resolver answers the access expiry; the portal stream closes before it | no |
