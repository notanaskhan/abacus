---
id: TASK-2217
title: T-01-T13 ADM-05 consent registry, part 1
spec: SPEC-501
acceptance_criteria: [AC-11]
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T13
branch: s17-t01-t13
created: 2026-10-30
updated: 2026-10-30
---

## Objective
ADM-05 frontend part 1 at /settings/consents on T1 inside the T12 frame (fixture mode): filter
chips, status tiles as filters, the note card, table with signer lines and status pills
(Requested with n of 2 signed, Expiring with days, Declined with no re-solicitation), footer
facts, selection bar; states a, b, f and g.

Acceptance (backlog row): "Scenario tests for a, b, f and g pass, tiles foot to 218, and no
Re-request control exists on a declined row."

## Done
- `screens/ADM-05/{index.tsx, copy.ts, scenarios.ts, ADM-05.test.tsx}`; route
  `/settings/consents` (flag `consents.registry`); manifest `fixture`; gallery registration.
- Fixtures: `seed/consents.ts` (the spec's 14 rows, 23 consents), `GET /v1/consents` handler
  (status incl. derived expiring, purpose, q), `scenarios/ADM-05.ts`.
- Contract (additive, regenerated): `ConsentOut.declined_at`, `revoked_at`, `signers`;
  `ConsentSignerOut.title` (DEC-1262).

## Progress log
- 2026-10-30: built in S17 Lane 2; tests run in the end review.
