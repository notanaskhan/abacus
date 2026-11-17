# C12 · TB hand-off into tax v1

| Field | Value |
|---|---|
| Register row | C12 in `docs/contracts/README.md` |
| Owner | ledger (T-06; SPEC-702 F6; DEC-66) |
| Status | stub (T-06-T05, 2026-11-17; DEC-5514) |
| Code | `backend/src/abacus/modules/ledger/tb_handoff_contract.py` (`tb_handoff_router`) |
| Flag | `tax.tb_handoff` (default off; off: 404; on: 501 until T-06-T20 and T39) |
| Fixtures | `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/tb_handoff_slice.py` (Granite Peak FY2026, Copperleaf `close_lock`) |
| Consumer tests | `backend/tests/contracts/c12_tb_handoff/` and `apps/web/src/fixtures/contracts/c12-tb-handoff.contract.test.ts` (T-06-T06) |
| Consumers | AUD-38 (audit), CLS-12 (C-02 `close_lock`), TXP-13 d and the TXP-02 banner (tax) |

**Source-agnostic.** `source_kind` ∈ `audit_release` (G8), `review_release` (an SSARS review's release, OQ-4), `close_lock` (a locked December close). The hand-off references the source snapshot and never copies it (P-40); nothing posts back to the source; a re-hand-off after archive writes nothing into the archived engagement (P-43).

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/engagements/{id}/tax-handoff/targets` | `tb_handoff.preview` | same-client returns, metadata only |
| `GET /v1/engagements/{id}/tax-handoff/preview?target_work_item_id=` | `tb_handoff.preview` | counts, review rows, book income, schedules, tax items, gate, `preview_hash` |
| `POST /v1/engagements/{id}/tax-handoffs` + `Idempotency-Key` | `tb_handoff.create` | 201; 409 `handoff_not_available`, `handoff_needs_review`, `preview_changed`; conditions `tb_handoff_source_released`, `same_client`; live human |
| `GET /v1/tb-handoffs/{id}` · `/{id}/mappings` | `tb_handoff.read` | details; the O4 128-row table |
| `GET /v1/tax-returns/{id}/handoff` | `tax_return.read` | the landing banner and M-1 starting point |

**Human-only:** create. **Status words:** `tb_handoff` (Not available, Needs review, Ready derived; Handed off; Superseded). **Audit events:** `tb_handoff.created|superseded`, `tax_issue.created`. **Outbox:** `tb_handoff.created`, `tb_handoff.superseded`, `tb_handoff.received` (tax). **Notifications:** `tb_handoff_received`, `tb_handoff_superseded`.

**Examples (foot):** Granite Peak FY2026: 121 + 5 + 2 = 128 accounts; book income 3,100,000 − 750,000 = 2,350,000; PP&E 6,050,000 + 1,380,000 − 1,050,000 = 6,380,000; accrued liabilities 1,630,000; passed AJE-3 68,400. Toast: "Handed off to FY2026 Form 1120 · 1 tax issue created · 7 accounts for the tax team to map".
