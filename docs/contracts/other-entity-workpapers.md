# Other entity workpapers v1 — 1120-S AAA, 1120 ASC 740, 990

| Field | Value |
|---|---|
| Owner | tax (T-06; SPEC-702) |
| Status | stub (T-06-T07, 2026-11-17; DEC-5516) |
| Code | `backend/src/abacus/modules/tax/entity_depth_contract.py` (`entity_depth_router`) |
| Flag | `tax.other_entity_workpapers` (default off; off: 404; on: 501 until each build task) |
| Fixtures | `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/entity_depth_slice.py` |
| Consumer tests | `backend/tests/contracts/t06_entity_depth/` and `apps/web/src/fixtures/contracts/t06-entity-depth.contract.test.ts` (T-06-T09) |

Every figure is TRI (`restricted`, `tri=True`): agents read it only with §7216 use and ai_disclosure in force (C19); nothing reaches the portal (INV-4). Client 404 → flag 404 → human-only 403 → 501.

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/tax-returns/{id}/schedules/aaa` | `other_workpapers.read` | TXP-13 a; read-only once Accepted |
| `GET …/provision?view=provision\|rate_reconciliation\|deferred` | `other_workpapers.read` | TXP-13 b, b2 |
| `POST …/provision/items/{item_id}/explain` | `issue.create` | SHL-15; classification only as a proposal |
| `GET …/functional-expenses?view=part_ix\|allocation_basis` | `other_workpapers.read` | TXP-13 c, c2 |
| `POST …/functional-expenses/allocation-runs` | `allocation_run.start` | c3; E12 allocates in code |

**Examples:** AAA 1,488,200; provision 2,134,650 + 122,550 = 2,257,200 (ETR 28.9%); Part IX 3,210,000 + 486,000 + 318,000 = 4,014,000; 80.0%; 87.4%.
