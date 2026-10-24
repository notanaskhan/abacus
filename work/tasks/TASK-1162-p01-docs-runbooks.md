---
id: TASK-1162
title: P-01 docs and runbooks — SHL-01/03/04/06 Deviations, registering a notification kind, the notification-email pause runbook, AuthKit and RB-22, the flag renewal calendar (P-01-T17)
spec: SPEC-013
acceptance_criteria: [AC-1]  # P-01 §8 items 7 and 8
risk_zone: green
status: done
epic: P-01
plan_key: P-01-T17
branch: s7-small-items-incidents
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Docs merge, `validate_docs` is green, and both flags have a renewal or retirement date before Mar 1, 2027."

## Done
- `docs/screens/SHL-01.md`: the interim Support (O2) frame under Deviations (the interim Go… was there). `SHL-03.md` and `SHL-04.md` already carried their Deviations (interim Go… for shortcuts; deferred inline actions); unchanged. `SHL-06.md`: DV-6 (`/engagements` landing until HOME-01, R6) and DV-7 (AuthKit capability gaps to verify, Q2), beside DV-1 hosted a–f.
- `backend/src/abacus/modules/notifications/README.md`: registering a kind (code rules, category, glyph, email default, inline actions, resolvers, the catalogue line, templates as content, the closed lists the tests pin, C16 additivity) and pausing email.
- C16 v1 frozen record: already recorded by P-01-T12 (`docs/contracts/notifications.md` status and `backend/tests/contracts/c16_notifications/v1.json`; register row frozen). Nothing to add.
- `docs/runbooks/RB-31-notification-email-pause.md` (drafted; index row added; Q-02-T51's unnumbered runbooks now start at RB-32).
- `docs/architecture/authkit-staff-sign-in.md`: the RB-22 section (what an AuthKit outage does to sign-in, refresh and step-up) and the Q2 gaps to verify.
- `docs/plan/status/flag-renewals-2027.md`: `notifications.v2` retirement and `notifications.email` renewal due Thu Feb 25, 2027; both flag descriptions point at it.

## Progress log
- 2026-10-24: written; `validate_docs` green. RB-22 itself is Q-01's (not written yet); the AuthKit doc links its index row.
