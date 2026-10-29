---
id: RB-41
title: Onboard a firm's client list (client import)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-05-27
---
# RB-41 · Onboard a firm's client list

Owner: firm-admin desk · Applies to: a new firm's first week, after RB-37 (people and walls) ·
Contracts (frozen v1, 2026-10-29): `docs/contracts/intake-import.md`, `clients.md`,
`contacts-access.md`, `engagements-v2.md`, `acceptance-independence.md` · Screens: CLI-06, CLI-01,
CLI-02, CLI-04, ENG-03 · Task: P-07-T64 (P-07 acceptance: "A fresh session can onboard a firm's
client list using only the runbook and the contract docs").

Use only this runbook and the five contracts. Every write is a person's act (the agent and the
system are refused) and is audited; the import's file is the firm's data and never leaves the
product. Synthetic data only on a rehearsal firm.

## 0. Before you start
- [ ] RB-37 is done: the firm admin, partners and managers exist and are signed in.
- [ ] `clients.v2` and `engagements.v2` are on for the firm (`python -m abacus_tools.flags`); with
  `clients.v2` off every route below answers 404.
- [ ] The firm admin has the export from their practice system (the CCH Axcess Tax client list, or a
  plain CSV: UTF-8, at most 5 MB and 2,000 rows) on their own machine.

## 1. Upload
1. `POST /v1/client-imports?source=cch_axcess_tax_export|csv&filename=<name>` with the file as the
   raw body (`client_import.run`; firm admin, partner, manager). Keep the import id.
2. `GET /v1/client-imports/{import_id}`: the import lands in `stage: reviewing` with `mapping`
   (column → field) and `counts` (`rows`, `matched`, `to_review`, `new`). Every cell is kept as
   inert text; on a firm that is not synthetic an SSN or ITIN is dropped, never stored, and its row
   carries `tin_kind_not_allowed`.

## 2. Decide every row that waits
1. `GET …/{import_id}/rows?review=…` lists the rows; a row scoring at or above 0.9 is already
   `merge`, a row with no candidate is `new`, the rest wait for a person (the rehearsal file: 212
   rows, 204 matched, 8 to review).
2. For each waiting row: `PUT …/{import_id}/rows/{row_id}/decision` `{decision, merge_client_id?}`
   with `new`, `merge` (into the match, or `merge_client_id`), `keep_both` (needs a match) or
   `skip`.
3. Done when `GET /v1/client-imports/{import_id}` shows `counts.to_review: 0`. An undecided row is
   skipped at run.

## 3. Run
1. `POST …/{import_id}/run` with an `Idempotency-Key` → 202. A second run is 409
   `import_already_run`.
2. `GET /v1/client-imports/{import_id}` reaches `stage: done` with `imported`, `skipped`, `new` and
   `failed`; a failed row keeps its `error_code` and the rest carry on. `merge` adds the row's contact
   when its email is new to the client and never changes a TIN.
3. Check one client in CLI-02 (`GET /v1/clients/{client_id}`): its TIN reads masked (the sealed
   value is never in a list or an export), and the audit names the person who ran the import (INV-5).

## 4. Contacts and portal access
1. Contacts arrive with the import where the file names them; add others with
   `POST /v1/clients/{client_id}/contacts` (`contact.manage`).
2. Invite only after the engagement exists (section 5): `POST /v1/contacts/{contact_id}/invitations`
   with an `Idempotency-Key` (`client_access.grant`, fresh second factor).

## 5. First engagements
1. ENG-03: `POST /v1/engagements/drafts`, validate, then create; acceptance and independence follow
   `docs/contracts/acceptance-independence.md` (G1, G2 before any client data is requested).

## 6. Evidence for the go-live dossier
- The import id, its final counts, and the delete-after date (the file is kept sealed 30 days,
  then erased).
- `client_import.row_decided` audit events, one per decided row, naming the person.

## Hand-off notes (P-07 → its consumers)
- **R-01, N-01, T-01, A-01** read clients and engagements only through `organisations.api` and
  `engagements.api` (`client_facts`, `masked_tin`, `gate_facts`, `independence_cleared`,
  `acceptance_decided_at`, `designate_contact`); never their tables.
- The five contracts are frozen at v1: an additive change needs no new version; anything else
  ships v2 beside v1 with overlap.
- The sealed TIN never leaves `organisations` unmasked except through the logged reveal (P-07-T10).
