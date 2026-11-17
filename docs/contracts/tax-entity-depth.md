# Tax entity depth v1 — fixed assets, book-tax, basis and decisions, states and PTET

| Field | Value |
|---|---|
| Owner | tax (T-06; SPEC-702) |
| Status | stub (T-06-T07, 2026-11-17; DEC-5516) |
| Code | `backend/src/abacus/modules/tax/entity_depth_contract.py` (`entity_depth_router`) |
| Flag | `tax.entity_depth` (default off; off: 404; on: 501 until each build task) |
| Fixtures | `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/entity_depth_slice.py` |
| Consumer tests | `backend/tests/contracts/t06_entity_depth/` and `apps/web/src/fixtures/contracts/t06-entity-depth.contract.test.ts` (T-06-T09) |

Every figure is TRI (`restricted`, `tri=True`): agents read it only with §7216 use and ai_disclosure in force (C19); nothing reaches the portal (INV-4). Client 404 → flag 404 → human-only 403 → 501.

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/tax-returns/{id}/fixed-assets?view=register\|by_property\|dispositions` | `fixed_asset.read` | TXP-03 a, b, d; E3 `engine_version`, `inputs_hash` |
| `GET …/fixed-assets/{asset_id}` | `fixed_asset.read` | a2 drawer |
| `POST …/fixed-assets` | `fixed_asset.create` | 409 `return_locked` |
| `POST …/fixed-assets/{asset_id}/changes` | `fixed_asset.propose_change` | C3 proposal (ghost value) |
| `GET …/schedules/m3` · `/m1` | `book_tax.read` | (a)+(b)+(c)=(d); M-1 never filed beside M-3; `/m2` is T-05's route |
| `GET …/basis?view=basis\|s752&partner=` | `basis.read` | TXP-08 a–c, e |
| `POST …/decision-cards` · `POST /v1/decision-cards/{id}/send-to-client` | `decision.raise` · `decision.send_to_client` | §754; once (409 `decision_already_sent`); condition `decision_owner_contact` |
| `GET …/states?view=` · `POST …/states/sourcing:propose` · `POST …/states/sourcing/undo` · `PATCH …/states/{state}/ptet` | `states.read` · `sourcing.propose` · `sourcing.approve` · `ptet.update` | TXP-09 |

**Examples (foot):** 733,500 = 169,500 + 360,000 + 204,000; land 3,600,000; 46.0 + 31.5 + 22.5 = 100.0; PTET 28,044 + 17,070 + 18,982 = 64,096; outside basis 17,943,095 with Pell Street II off 28,595.
