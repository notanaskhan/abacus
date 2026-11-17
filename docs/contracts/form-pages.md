# Form pages v1 — the TAX-11 draft preview

| Field | Value |
|---|---|
| Owner | tax (T-06; SPEC-702) |
| Status | stub (T-06-T07, 2026-11-17; DEC-5516) |
| Code | `backend/src/abacus/modules/tax/entity_depth_contract.py` (`entity_depth_router`) |
| Flag | `tax.form_preview` (default off; off: 404; on: 501 until each build task) |
| Fixtures | `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/entity_depth_slice.py` |
| Consumer tests | `backend/tests/contracts/t06_entity_depth/` and `apps/web/src/fixtures/contracts/t06-entity-depth.contract.test.ts` (T-06-T09) |

Every figure is TRI (`restricted`, `tri=True`): agents read it only with §7216 use and ai_disclosure in force (C19); nothing reaches the portal (INV-4). Client 404 → flag 404 → human-only 403 → 501.

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/tax-returns/{id}/form-pages?checkpoint=` | `form_preview.read` | from an approved checkpoint; "Draft — not for filing"; 409 `form_template_missing` |
| `GET …/form-pages/{page_key}/fields` · `GET …/fields/{field_key}/trace` | `form_preview.read` | field manifest; SHL-09 trace |
| `GET …/diagnostics` | `form_preview.read` | each linked to an existing issue by `rule_key` |
| `GET …/k1-previews` | `k1_package.read` | Σ box 2 = Schedule K line 2 |
| `POST …/form-pages:download-draft` | `form_preview.download_draft` | fresh MFA; audited (DEC-60); no transmit |

**Example:** Σ box 2 24,632 + 468,008 + 400,270 + 30,790 + 307,900 = 1,231,600 = Schedule K line 2. Final approval refuses 409 `blocking_diagnostics` while any blocks (T-06-T37). Page images (`.png`) land with the renderer (T-06-T44).
