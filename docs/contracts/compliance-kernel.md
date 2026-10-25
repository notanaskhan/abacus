# Compliance kernel (v1.1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` |
| Version | v1.1 (Q-02-T38: the firm-export stub joins the live incident, retention and hold halves) |
| Status | stub (firm export, Q-02-T38, 2026-10-25); live halves as listed in §1 |
| Provider epic | Q-02 (`evidence`, `platform`) |
| Consumers | G-02 (ADM-06 a to h: G-02-T11 stub, T12 suite, T16 screen, T18 incidents, T19 schedule), Q-02-T43 (implements the export), Q-02-T46 (independent ACs), Q-05 (FIL-02 reads of policies and holds) |
| Freeze sprint | S9 (the sprint G-02 consumes it); Q-02-T43 makes the export live behind it |
| Flag | `compliance.firm_export` (export routes; off: 404, on: 501 until Q-02-T43), `compliance.incidents`, `compliance.legal_holds` |
| Spec | Q-02 §3.9, §4.2, §4.3, §5.1 (`docs/plan/epics/Q-02.md`); AC-38 to AC-42 |
| ADRs | ADR-097, ADR-004, ADR-031, ADR-139; DEC-71 / P-14, DEC-72 (conflict C-11), DEC-227, DEC-290 |

## 1. Purpose
One index for what G-02's security center and Q-05's records screens build on: the incident register with its FTC clock, retention policies, legal holds, and the dual-approval firm export. Each half keeps its own contract file; this file fixes the firm-export stub and the versions consumers test against.

| Half | Contract | Version | State |
|---|---|---|---|
| Incident create with the clock (`ftc_notify_by`, `clock_day`, `clock_days`, `notification_event`) | `security-incidents.md` | v0.1 | live behind `compliance.incidents` (Q-02-T33) |
| Retention policies read and save | `retention.md` | v1 | live (Q-02-T23) |
| Legal holds read, place and lift | `legal-holds.md` | v1 | live behind `compliance.legal_holds` (Q-02-T29) |
| Firm export request, approve, decline, link and list | this file §2 to §4 | v1.1 | stub behind `compliance.firm_export` (Q-02-T38) |

## 2. Who may call it (firm export)
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| List the last 12 exports | `GET /v1/firm/data-exports` | `firm_export.read` | firm admin, security admin, partner-level members | denied |
| Request an export | `POST /v1/firm/data-exports` → 202 (`Idempotency-Key`) | `firm_export.request` (fresh MFA) | security admin | denied |
| Approve | `POST /v1/firm/data-exports/{export_id}/approve` | `firm_export.approve` (fresh MFA) | the named approver: security admin or partner level, never the requester | denied |
| Decline | `POST /v1/firm/data-exports/{export_id}/decline` | `firm_export.approve` (fresh MFA) | the named approver | denied |
| A download link | `POST /v1/firm/data-exports/{export_id}/link` | `firm_export.download` (fresh MFA) | the requester or the approver | denied |

## 3. Models
Code: `backend/src/abacus/modules/evidence/firm_export_contract.py`. Internal unless stated.
- **`FirmExportRequestIn`** `{approver_user_id, scope = "all"}` (extras refused). v1 exports everything (ADM-06 b "Export all firm data?").
- **`FirmExportDeclineIn`** `{reason?}` (one line, at most 500, Confidential).
- **`FirmExportOut`** `{id, status, scope, origin (on_demand · scheduled), requested_by {user_id, display_name (Confidential)}, requested_at, approver {…}, decided_at?, ready_at?, available_until? (the 7-day window), size_bytes?, manifest_sha256?}`.
- **`FirmExportPageOut`** `{items}` (at most 12, newest first).
- **`FirmExportLinkOut`** `{url (Restricted, never logged), expires_at (15 minutes), manifest_sha256}`.

## 4. Status codes and errors
`status`: `awaiting_approval` → `building` → `ready` → `downloaded` · `expired` (the window ends) · `declined` · `failed`. These are the contract's codes; the words ("Waiting for approval · Margaret Okonkwo", "Scheduled") are G-02's screen copy, registered in the status vocabulary when G-02-T11 adds the card.

| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | flag off; an export of another firm or none |
| 422 | `approver_invalid` | the approver is the requester, or no security admin or partner-level member |
| 409 | `approver_must_differ` · `export_not_awaiting_approval` · `export_not_ready` | the requester decides; a decided export; a link before the archive is built |
| 410 | `export_expired` | a link after the 7 days |
| 501 | `not_implemented` | the stub, flag on, until Q-02-T43 |

## 5. Human-only actions
`firm_export.request`, `firm_export.approve` and `firm_export.download` deny the agent and system at the matrix; `firm_export.approved` is on the human-only register (Q-02 AC-17). Two distinct people are needed (DEC-72): the service refuses the requester as approver, and the table's CHECKs refuse it again (Q-02-T43).

## 6. Fixtures (seed-derived)
`apps/web/src/fixtures/seed/compliance.ts` and `handlers/compliance.ts` (fixture mode), mirrored by `backend/tests/contracts/compliance_kernel/`: INC-2026-005 "Credential-stuffing attempts against client portal sign-in", discovered Thu Sep 10, 2026 2:14 AM CT, 0 confirmed, Day 4 of 30 and notify by Sat Oct 10 at E0 (Mon Sep 14, 2026, 9:24 AM CT); the monthly history Sep 1 386 GB, Aug 1 371 GB, Jul 1 359 GB (each at 2:00 AM CT, its 7 days over by E0, so `expired`); Felix Andersen's request "Waiting for approval · Margaret Okonkwo". The incident timeline, two-person decisions and the schedule are G-02's (G-02-T18, T19).

## 7. Audit and outbox (Q-02-T43)
`firm_export.requested`, `firm_export.approved`, `firm_export.declined`, `firm_export.ready` (system), `firm_export.downloaded`; notifications `firm_export_approval_requested` (the named approver) and `firm_export_ready` (requester and approver). Identifiers only.
