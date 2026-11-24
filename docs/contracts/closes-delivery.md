# Closes delivery v1 — CAS package, tax hand-off, information returns

| Field | Value |
|---|---|
| Register row | closes-delivery in `docs/contracts/README.md` (C-02) |
| Owner | closes (C-02; SPEC-701) |
| Status | stub (C-02-T07, 2026-11-17; DEC-5506) |
| Code | `backend/src/abacus/modules/closes/delivery_contract.py` (`delivery_router`) |
| Flags | `closes.delivery` (CLS-08), `closes.tax_handoff` (CLS-12), `closes.information_returns` (CLS-13); default off; off: 404; on: 501 until each build task |
| Consumers | CLS-08, CLS-12, CLS-13 (AY); POR-08 / POR-09 (the Copperleaf package swap); R-02 (C18 kind `close_package`); T-06 (C12 `receive_tb_handoff`) |

## Operations

| Method and path | Action | Build task |
|---|---|---|
| `GET /v1/closes/{id}/package` | `close_package.read` | T21 |
| `PATCH /v1/closes/{id}/package` · `PATCH …/package/commentary` | `close_package.edit` | T21 |
| `POST /v1/closes/{id}/package/generate` (202) · `GET …/package/pages/{n}` | `close_package.generate` · `.read` | T21 |
| `GET /v1/closes/{id}/package.pdf` · `.xlsx` | `close_package.export` | T21 |
| `POST /v1/closes/{id}/package/release` (202, `Idempotency-Key`) | `close_package.release` | T23 |
| `POST /v1/closes/{id}/lock` · `POST /v1/closes/{id}/reopen` | `close.lock` · `close.reopen` | T29 |
| `GET /v1/closes/{id}/tax-handoff` · `POST …` (202, `Idempotency-Key`) | `tax_handoff.read` · `.publish` | T39 |
| `GET /v1/client-entities/{eid}/information-returns?tax_year=` | `information_returns.read` | T45 |
| `GET /v1/vendors/{id}` | `information_returns.read` (last four only; nulled offshore) | T33 |
| `PUT /v1/vendors/{id}/w9 {tin, tin_kind, evidence_version_id, signed_on, expected_version}` | `vendor_1099.update` (sealed on arrival, never echoed; 409 `tin_conflict`, `stale_version`; 422 `tin_invalid`, `tin_kind_not_allowed`, `evidence_required`) | T33 (DEC-5907) |
| `PATCH /v1/vendors/{id}` | `vendor_1099.update` | T45 |
| `POST /v1/vendors/{id}/tin:reveal` | `tin.reveal` (organisations' action, `not_offshore`, fresh MFA); P-03's field reveal, one `pii_reveals` row (`vendor:<id>:tin`) naming the person; 403 `tin_reveal_refused` | T33 |
| `POST /v1/client-entities/{eid}/w9-requests` | `w9.request` | T33 |
| `POST /v1/vendors/{id}/tin-match-results` · `…/backup-withholding {event, reason, evidence_version_id, notice_received_on}` | `tin_match.record` · `backup_withholding.record` (409 `tin_not_on_file`, `backup_withholding_not_due`, `backup_withholding_state`) | T33 |
| `POST /v1/information-return-batches` | `information_return_batch.approve` | T46 |
| `GET /v1/information-return-batches/{id}/iris.csv` | `information_return_batch.export` | T46 |
| `POST …/{id}/filed` · `POST …/{id}/acknowledgement` | `.record_filing` · `.record_ack` | T46 |

The client's package decision is R-02's C18 applier (`close_package.client_decide`, portal).
There is **no transmit route** (R-04; IRIS-001; the route-table test proves it).

## Status words
`close_deliverable` (Drafting, Draft, Released, Approved by client), `close` (Approved, Delivered,
Locked), `tax_handoff`, `w9_status`, `information_return_batch` (C-02-T03).

## Human-only actions and audit events
Every write above is a person's (agent and system denied). Audit: `close_package.generated|
regenerated|commentary_edited|released|client_approved|exported`, `close.approved|delivered|
locked|reopened`, `tax_handoff.published|superseded`, `vendor.updated`, `w9.requested`,
`tin.revealed` (through `pii_reveals`), `tin_match.recorded`, `backup_withholding.recorded`,
`information_return_batch.approved|exported|filed|acknowledged`. Values stay out (DEC-60).

## Examples (seed; foot)
- Package (CLS-08a): current assets 337,135.45 + net PP&E 212,060.00 = 549,195.45 = liabilities 184,983.05 + equity 364,212.40; revenue 214,600 − COGS 84,860 = 129,740; − 101,425 = 28,315; − 520 = 27,795 (July 31,455). Route AR-C 70 preparation; legend "No assurance is provided.".
- Hand-off (CLS-12a): TB v1, year ended Dec 31, 2026; fixed asset register 278,400.00 · 74,900.00 · 25,680.00; 3 tax issues.
- 1099 (CLS-13a): 12 vendors paid, 6 reportable (78,400.00 + 25,600.00 + 5,840.00 + 4,200.00 + 3,600.00 + 2,640.00), 2 requested, 1 TIN mismatch, 0 filed; threshold $2,000 for 2026 payments from the rules table.
