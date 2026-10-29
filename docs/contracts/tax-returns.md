# Tax returns (v1; C1 additive)

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-02-T01, 2026-10-29): every route 501 behind `tax.returns_v1` |
| Provider epic | T-02 |
| Consumers | TAX-01, TAX-02, TAX-03 (T-02), HOME-01/02 (C13), T-01 (sync state through `tax.api.record_sync_state`), T-08 |
| Spec | SPEC-502 AC-4; `docs/plan/epics/T-02.md` §4.3 |
| ADRs | ADR-231, ADR-190 (bare status codes), DEC-43 (walls 404, no counts) |

## 1. Routes
| Operation | Method and path | Action |
|---|---|---|
| TAX-01 rows (filters `tax_year, status[], review_level, form[], office[], partner, preparer, due_within_days, q, group_by=office`; sort `extended_due`, `client`) | `GET /v1/tax-returns` | `tax_return.read_metadata` |
| Tiles, open/done/extended, office totals | `GET /v1/tax-returns/summary` | `tax_return.read_metadata` |
| The `ReturnFrame` record | `GET /v1/tax-returns/{id}` | `tax_return.read_metadata` |
| TAX-02 overview | `GET /v1/tax-returns/{id}/overview` | `tax_return.read` |
| TAX-03 intake | `GET /v1/tax-returns/{id}/intake` | `tax_return.read` |
| Assign preparer, reviewer or signer | `POST /v1/tax-returns:bulk-assign` (Idempotency-Key), `POST /v1/tax-returns/{id}/assignments` | `tax_return.assign` |
| `start_preparation`, `start_review` (409 `{gate}` for a person-gated move) | `POST /v1/tax-returns/{id}/transitions` | `tax_return.status_change` |

Final approval is T-01's (`docs/contracts/tax-engine-bridge.md`); T-02 calls it through `tax.api` and declares none of its routes.

## 2. Status words
The registry's `return` object (blueprint §3.3.1; "Ready" is `approved`'s tile word; Draft and Working are `preparing`'s subbar words) and `return_flag` (extended, on hold, superseded, amended); the sync chip is `return_sync_chip`.

## 3. Classification
Engine figures TRI (shown only from approved imports, ADR-231); client and people names confidential; no TIN.

## 4. Events
Outbox: `tax_return.status_changed`, `tax_return.assigned`. Audit: `tax_return.assigned`, `tax_return.status_changed` (with the actor grammar of INV-5).

## Live since T-02-T09 (DEC-1259)
- `GET /v1/tax-returns`, `/summary` and `POST :bulk-assign` are live (`tax/board.py`, routes in `tax/returns_routes.py`); the record, overview, intake, single assignment and transitions stay 501 until T-02-T13.
- Composition: `tax_returns` with `engagements.api.work_item_facts(ctx, "tax_return")` (wall-safe; client name, office, people by function). Done = `filed`, `accepted`.
- One page: a season's board is returned whole (`cursor` reserved, `next_cursor` null).
- `due_rule_code` stays null until T-02-T10 pins the rule text with the dates.

- T-02-T14 (additive): `TaxReturnRecordOut.card_detail` and `engine_url`; `TaxReturnOverviewOut` gains `record_links`, `filing`, `pipeline`, `engine_synced_on`, `engine_footnote`, `pro_forma_label`, `pro_forma`, `plan`, `k1_classifications`, `carryforwards`, `issues` and `two_year`; `EngineSummaryLineOut` gains the statement grammar (`line_ref`, `indent`, `total`, `note`, `issue`) and a nullable `amount`; `LadderStepOut` gains `step`, `state`, `note`, `blocked_by`; `K1DependencyOut` gains `source_label`, `short_name`, `source_due_on`. Every new list defaults to empty, and an empty list draws no band or card. T-02-T13's read model fills them.
