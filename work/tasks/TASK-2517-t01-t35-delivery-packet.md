---
id: TASK-2517
title: T-01-T35 Delivery checklist and packet (TAX-12 a, b)
spec: SPEC-501  # T-01 §3.11; tax-engine-bridge; efile-record
acceptance_criteria: [AC-3.11]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T35
branch: s20b-t01-t35
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Delivery checklist and packet: GET /v1/tax-returns/{id}/delivery; migration delivery_packets;
assemble from engine PDFs plus a cover letter rendered from a database template through C11 (no
model text, ADR P-25 off), toggle items, regenerate the letter by re-rendering, approve by the
signer or a manager (DEC-38) with client_service preparing; payment instructions read model from
the approved import checkpoint.

Acceptance (backlog row): "The Feld packet lists the client copy, letter, 8879 with TR-579-IT and
two vouchers, Grace Holloway cannot approve it, and no gateway call occurs during assembly."

## Plan (red)
- Migration **0523** `delivery_packets` (revises 0522): versions per return, one open packet,
  column-level UPDATE on items, letter, status, approver, row_version; a guard trigger moves the
  status only forward, freezes approved and superseded rows, refuses deletes. Forced RLS.
- `tax/delivery.py` (red): read model, assemble, toggle, regenerate letter, approve; the letter is
  C11 kind `delivery_cover_letter` from the firm's published template, values code fills.
- `tax/engine_contract.py`: the five routes live behind `tax.delivery_efile`.
- Registry, schema-check contract, tenant-isolation list, human-only `delivery_packet.approved`,
  `make regenerate`.
- **Stacked** on P-11-T13 (template import works against the grants) and P-11-T11 (the letter's
  render job), so 0523 chains after 0522.
- Security: a person only for every write (agent, system, support refused before the matrix);
  approve is the matrix's engagement partner or manager (Grace, client_service, gets 403); no
  gateway import in the module; TRI items never logged.
- Rollback: the flag; 0523 is expand-only.

## Decisions
DEC-1565.

## Progress log
- `2026-10-31` — Built on `s20b-t01-t35` (stacked on `s20b-p11-t13`). test_t01t35: 6 passed.
