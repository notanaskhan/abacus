# E-file record (v1)

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-01-T02, 2026-10-29): every route 501 behind `tax.delivery_efile` |
| Provider epic | T-01 |
| Consumers | T-02 (status machine), N-02 (C7 envelopes, retention extension), R-01/P-08 (client delivery), T-08 |
| Spec | SPEC-501 AC-5 to AC-8; `docs/plan/epics/T-01.md` §3.11–§3.15 |
| ADRs | ADR-231; R-04 (never ERO or transmitter); DEC-85 (Pub 1345 tolerances via C21) |

## 1. Purpose
Accrued records the e-file lifecycle; it **never transmits** (R-04). The ERO transmits in the engine; Accrued records who, when, which jurisdictions and the acknowledgements. The 8879 is signed against an **amount binding**; drift beyond the Pub 1345 tolerances (`platform.api.pub1345_tolerances`, C21) supersedes the binding and relocks.

## 2. Routes
| Operation | Method and path | Action |
|---|---|---|
| Delivery checklist and payments | `GET /v1/tax-returns/{id}/delivery` | `tax_return.read` |
| Assemble · edit · regenerate letter | `POST /v1/tax-returns/{id}/delivery-packet:assemble` · `PATCH /v1/delivery-packets/{id}` · `POST …/letter:regenerate` | `delivery_packet.prepare` |
| Approve the packet (DEC-38) | `POST /v1/delivery-packets/{id}/approve` | `delivery_packet.approve` |
| 8879 envelope with the binding (C7) | `POST /v1/tax-returns/{id}/efile-envelope` | `delivery_packet.prepare` |
| Tell the ERO it is ready | `POST /v1/tax-returns/{id}/ero-notices` | `delivery_packet.prepare` |
| The ERO's record (409 `signatures_incomplete`, `binding_superseded`, `not_synced`) | `POST /v1/tax-returns/{id}/transmissions` | `transmission.record` (`function_in(signer)`; `ero_designated` in the service; human only) |
| Manual ack with evidence | `POST /v1/tax-returns/{id}/acks` | `efile_ack.record` |
| A rejection as an issue; Rejected to Fixing (409 `not_rejected`; T-01-T37, DEC-1570) | `POST /v1/tax-returns/{id}/acks/{ack_id}/issue` | `efile_ack.record` |
| Release the client copy | `POST /v1/tax-returns/{id}/deliverables:publish` | `deliverable.publish` |
| ERO designation | `PUT /v1/firm/members/{id}/ero` | `member.set_ero` (firm admin, fresh MFA) |

## 3. Never ERO
No MeF, A2A, ETIN, EFIN or IRIS TCC identifier, and no IRS or state host, anywhere (NEVER-ERO-001, T-01-T07). A submission id is served by its last four only.

## 4. Events
Outbox: `efile_binding.superseded`, `transmission.recorded`, `filing.acknowledged`, `return.delivered`. Audit: `delivery_packet.assembled`, `.approved`, `efile.binding_recorded`, `.relocked`, `transmission.recorded`, `efile_ack.recorded`, `deliverable.published`, `member.ero_set`.
