# Tax schedules: extensions, estimates and payments

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub behind `tax.extensions_estimates` (T-03-T02, 2026-11-03, DEC-2201): 404 off, 501 on until T-03-T07; freeze Fri Oct 29, 2027 |
| Provider epic | T-03 (no C-id) |
| Consumers | TAX-13; T-08 (HOME-03), R-03 (POR-10), T-04 (TAX-12 estimate reminders) |
| Spec | SPEC-643 AC-4, AC-7, AC-9; `docs/plan/epics/T-03.md` §4.3 |
| Module | `tax/schedules_contract.py` |

## 1. Routes
| Operation | Method and path | Action |
|---|---|---|
| Extensions per return with jurisdiction lines; `counts` {extended, open, filed, likely, acks_pending} from visible rows | `GET /v1/tax/extensions?tax_year=&segment=open\|filed\|likely&tile=&q=&cursor=` | `filing_extension.read` |
| Detail (payments, approvals, confirmation, evidence, rule and engine versions) | `GET /v1/tax/extensions/{id}` | `filing_extension.read` |
| Prepare (409 `gate_unmet` with G1/G3 facts) · submit for approval (C13 gate) | `POST /v1/tax/extensions:prepare` · `:submit-for-approval` | `filing_extension.prepare` |
| Approve and request (one unit of work; human only; Idempotency-Key) | `POST /v1/tax/extensions:approve-and-request` | `filing_extension.approve_payment` and `.confirmation_send` |
| Record filed in the engine · likely to extend (If-Match) | `PATCH /v1/tax/extensions/{id}` | `filing_extension.mark_filed` · `.flag_likely` |
| One confirmation request | `POST /v1/tax/extensions/{id}/confirmation-requests` | `filing_extension.confirmation_send` |
| Estimates by quarter; `counts` {due, paid, scheduled, confirmation_requested, not_required} | `GET /v1/tax/estimates?tax_year=&quarter=&tile=&q=` | `estimate_schedule.read` |
| Inputs (recompute) · an installment (If-Match) | `PATCH /v1/tax/estimates/{id}` · `PATCH …/installments/{quarter}` | `estimate_schedule.update` |
| Confirmation request · follow-up draft (sent by a person, `follow_up.send`) | `POST …/installments/{quarter}/confirmation-requests` · `…/follow-ups` | `estimate_schedule.confirmation_send` · `follow_up.draft` |
| DF-08 payments union (read only) | `GET /v1/tax/payments?tax_year=` | `filing_extension.read` |
| Excel exports of the visible rows (fresh MFA) | `GET /v1/tax/extensions/export.xlsx` · `GET /v1/tax/estimates/export.xlsx` | `tax_schedule.export` |

Every route answers 404 to a client principal. POR-10 reads confirmation requests through its
own request grant.

## 2. Python API (T-03-T07)
`tax.api.extension_for(tax_return_id)`, `estimates_for(client_entity_id, tax_year)` and
`installments_due(range)`.

## 3. Rules
- Code computes projected liability, safe-harbor targets, paid-by-original-due checks, annual
  required payments and installments (`tax.compute.payments`, T-03-T04). Every computed figure
  carries `stamp` (engine name, version, inputs hash). Cells show no "$".
- Accrued never transmits (DEC-49). "Mark filed" records what a person filed in the engine, and
  the ack import (T-03-T08) moves it to Accepted or Rejected.
- Payment methods are labels, never instruments (DEC-89). No route stores bank details.
- An approved extension payment never changes. A later change is a new payment that supersedes it.
- Confirmation requests are request items ("Send confirmation requests"), never tasks.

## 4. Status words
`filing_extension`: Not filed · Prepared · Filed · Accepted · Rejected. `estimate_installment`:
Not confirmed · Confirmation requested · Scheduled {date} · Paid {date} · Not required.

## 5. Classification
Every amount and reject code is TRI. Client and contact names are confidential. Rules and
versions are internal.

## 6. Pen test #2 scope note
These routes and the questionnaire editor routes (`questionnaires.md`, T-03 additive) are listed
for pen test #2 (Q-03-T166). The pen test itself is deferred under DEC-1389
(`docs/plan/status/pen-test-deferral.md`).
