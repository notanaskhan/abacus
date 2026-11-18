# Tax practice tools v1 (TP-1) — two-year, standards runs, planning, amendments and AARs

| Field | Value |
|---|---|
| Owner | tax (T-08; SPEC-710) |
| Status | stub (T-08-T04, 2026-11-18; DEC-5603); v1 S54 |
| Code | `backend/src/abacus/modules/tax/practice_tools_contract.py` (`practice_tools_router`) |
| Flags | `tax.two_year`, `tax.standards_runs`, `tax.planning`, `tax.amendments` (default off; off: 404; on: 501) |
| Consumers | TAX-10, TAX-14, TAX-15, TAX-16; N-03 (raise); T-09 (accepted opportunities) |

Every figure, explanation, rationale and name is TRI: agents read it only with §7216 use and ai_disclosure in force (C19). Client 404 → flag 404 → human-only 403 → 501. Δ, Δ%, check differences, savings and amendment changes are code; tax and the imputed underpayment are engine imports or a labelled shadow tie-out (DEC-77).

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/tax-returns/{id}/two-year?filter=all\|over_threshold` | `tax_return.read` | lines, threshold source and version, tally |
| `POST …/two-year:explain` | `two_year.explain` | 409 `consent_7216_missing` |
| `PUT …/two-year/lines/{line_key}/explanation` · `POST …/explanation:accept` | `variance_explanation.edit` · `variance_explanation.accept` | accept pins `values_hash`; 409 `explanation_stale` |
| `GET …/two-year.xlsx` | `export.create` | deterministic |
| `GET /v1/standards-runs` · `/{rid}` · `/{rid}/items/{work_item_id}/checks` | `standards_run.read` | tiles, progress, checks (`1065-v4/C-17`) |
| `POST /v1/standards-runs` · `POST …/{rid}:rerun` | `standards_run.start` | model-free; 422 `check_code_unknown` on import |
| `POST /v1/standards-check-results/{id}:confirm` | `standards_check.confirm` | manual items, human-only |
| `GET /v1/planning-summary` · `/planning-opportunities` · `/{oid}` | `planning.read` | strip, queue, detail |
| `POST …/{oid}:prepare-raise` · `:raise` | `planning.raise` | database template (P-25 not accepted); a person's send |
| `POST …/{oid}:create-project` | `planning.create_project` | ENG-03 prefill only |
| `POST …/{oid}:decline` · `:dismiss` · `:restore` · `POST /v1/planning-opportunities` | `planning.dismiss` · `planning.create` | reason required; insert-only events |
| `POST /v1/tax-returns/{id}/amendments` · `GET /v1/amendments/{aid}?jurisdiction=` · `PUT …/explanation` · `POST …/proposals:draft` | `amendment.create` · `tax_return.read` · `amendment.edit` | 409 `return_accepted` writes to the original |
| `POST /v1/tax-returns/{id}/aars` · `GET /v1/aars/{xid}` · `POST …/recommendation:draft` | `aar.create` · `tax_return.read` | the election is the signer's `decision.decide` (409 `not_bba_signer`) |

**Examples (foot):** AGI 598,030 = 268,400 + 6,910 + 14,820 + 307,900; 8 flagged; refund due 2,708 = 41,000 − 37,678 − 614; IL (495) = 11,999 − 12,494; 14,800 = 40,000 × 37%.
