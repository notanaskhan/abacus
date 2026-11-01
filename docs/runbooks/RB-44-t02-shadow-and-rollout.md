---
id: RB-44
title: T-02 returns, organizers and K-1s — pilot onboarding, shadow and the two flips
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-08-13
---
# RB-44 · T-02 pilot onboarding, shadow reconciliation and the two flips

| Field | Value |
|---|---|
| Owner | builder; the other founder approves each flip (T-02-T34's acceptance) |
| Severity range | SEV3 (one firm); SEV2 if a flip goes wrong inside the Sep 1 – Oct 20 window |
| Linked from | the pilot calendar (`docs/ops/pilot/README.md`), `firm-rollback.md` |
| SLO affected | none during shadow; the tax routes' SLOs after each flip |
| Kill switches that apply | `tax.returns_v1`, `questionnaires.v1`, `evidence.duplicate_review` (Aug 17); `tax.k1_release` (Aug 31). Per firm, Tuesday 19:00 CT slot only |
| Rehearse by | Fri Aug 13, 2027, once on staging on the synthetic test firm (both founders present) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Firm content comes in through the product (import endpoints and admin screens), never a seed
file or a commit (AGENTS 16). Rehearse on the synthetic test firm; the pilot firm is the same
procedure on its own tenant.

## 1. Pilot onboarding (before Tue Jul 27)
1. **Returns:** CLI-06's client import (CCH client list), then each return's engine link through
   TAX-09 (a person marks the first export). RB-41 is the import's runbook.
2. **Organizer templates:** `POST /v1/questionnaire-templates:import` (CSV, dry run first; markup,
   formulas and template expressions are refused), then publish the version.
3. **Recipient contacts:** each K-1 recipient's delivery contact on the issuing client (CLI-04),
   e-furnishing consent recorded where the recipient gave it.
4. Entitlement: the firm's `tax` module row (P-28) — a database row, not a flag.

## 2. Shadow (Tue Jul 27 – Fri Aug 13, staff only)
Flags on for staff only; clients see nothing. Each business day, for every pilot return, reconcile
against CCH Axcess and record the result in the pilot log (counts and return ids only):
- [ ] TAX-01 board: the return exists, status and stage match CCH's.
- [ ] TAX-02: preparer, reviewer and signer match; due date and extension match CCH.
- [ ] TAX-03: every source document in CCH is a satisfied request; nothing extra.
- [ ] TXP-12 (entity returns): the K-1 set's recipients, TIN last four and box 1/2/5/18A match the
      engine's final set; drafts shared match the receiving returns.
- [ ] TAX-09: last export and last import times match the engine's history.
Any mismatch: an issue on the return, root cause before the next day's run. Three clean days in a
row are the gate for the Aug 17 flip.

## 3. Flip 1 · Tue Aug 17, 19:00 CT — `tax.returns_v1`, `questionnaires.v1`, `evidence.duplicate_review`
- **Go:** shadow gate met; both founders approve in the pilot log; no deploy in flight.
- **Do:** flip the three flags for the pilot firm only (protected registry change, one PR).
- **Check (30 min):** TAX-01 loads for the firm's staff; a client opens POR-05 and autosaves; a
  duplicate upload is accepted and flagged.
- **Rollback (written, any time):** flags off for the firm (one PR); the routes answer 404 and
  the nav area hides; nothing is deleted — answers, imports and duplicates stay recorded.
  Clients lose POR-05 until the next flip; tell the firm's admin before the slot ends.

## 4. Flag renewal · Tue Aug 24
The four flags expire Mon Aug 30, 2027. Renew all four in one protected bundle to Mon Nov 22,
2027 (outside Sep 1 – Oct 20). RB-26 is the generic procedure. Miss it and `make check-fast` goes
red for everyone on Aug 30.

## 5. Flip 2 · Tue Aug 31, 19:00 CT — `tax.k1_release`
- **Go:** Flip 1 stable a week; RB-45 rehearsed; both founders approve.
- **Do:** flip `tax.k1_release` for the pilot firm.
- **Check:** a person releases one synthetic package set on the test firm in production shape
  (Undo inside ten seconds works), the recipient sees only their own package on POR-13.
- **Rollback:** flag off: TXP-12's release and resend and the portal K-1 routes answer 404.
  Released packages stay released and their access events stay; RB-45 covers a mis-release.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
