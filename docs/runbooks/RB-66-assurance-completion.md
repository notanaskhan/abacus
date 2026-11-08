---
id: RB-66
title: "Assurance completion: the assurance_completion entitlement, the completion schema before Dec 24, and rollback"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-12-17
---
# RB-66 · Assurance completion

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (a firm sees the completion screens a day late) to SEV2 (a firm without the module reaches them) |
| Source | A-06-T37; A-06 §4.9; DEC-2714 |

## What changed
A-06's completion family (AUD-15 findings, AUD-16 misstatements and adjustments, AUD-17 review
notes and sign-off matrix, AUD-20 statements and disclosure checklist) is the `assurance_completion`
entitlement (ADR P-28). The rollout flags `assurance.completion` and `adjustments.entries` are
retired; migration 0713 gave every firm that had either flag on its entitlement row.

## Before Dec 24, 2027 (schema cut)
1. Confirm migrations through 0713 are on production (`alembic current`); only expand-only
   migrations queue after Dec 24 until Apr 20 (Q-04-T111).
2. `SELECT tenant_id FROM tenant_entitlements WHERE module = 'assurance_completion'` lists every
   firm that had the flags on.

## Turning a firm on or off
- On: write the entitlement row through the platform's entitlement route (staff, two people).
- Off: end the row (`valid_to`); the routes answer 404 and the screens show their flag-off state.
  Rows already written (findings, entries, notes, statements) persist.

## Rollback
Downgrading 0713 deletes the entitlement rows; the code then refuses every completion route. Prefer
ending one firm's row over a downgrade.
