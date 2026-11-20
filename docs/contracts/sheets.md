# SH-1 · Sheets (C23) v1 — stub

| Field | Value |
|---|---|
| Register row | C23 in `docs/contracts/README.md` (K-03-T01, DEC-5810) |
| Owner | workpapers (K-03; SPEC-721; ADR-162/345) |
| Status | stub (K-03-T09, 2026-11-20; DEC-5850) |
| Code | `backend/src/abacus/modules/workpapers/sheets_contract.py` (`sheets_router`) |
| Flags | `sheets.enabled`; agent-column routes also `agent_columns.enabled` (default off; off: 404; on: 501) |
| View model | F-08's `SheetVM` (`packages/ui/src/sheet/types.ts`); `apps/web/src/domain/sheets/vm.ts` (`toSheetVM`) maps the generated client into it |
| Fixtures | `apps/web/src/fixtures/seed/sheets-sh1.ts` (from the F-08-T02 SURL seed); scenarios `SHT-01`, `SHT-02`, `SHT-04` (17 artboards) |
| Consumer tests | `backend/tests/contracts/sh1_sheets/` and `apps/web/src/fixtures/contracts/sh1-sheets.contract.test.ts` (K-03-T10) |

| Method · path | Action | Notes |
|---|---|---|
| `POST /v1/work-items/{wid}/sheets {procedure_id, sheet_definition_ref}` | `sheet.configure` | manual create |
| `GET /v1/sheets/{sid}` · `GET …/rows?view=&cursor=` | `sheet.read` | SheetVM: columns, sections with totals, rows, cell states, sign-off state, status bar |
| `POST …/rows/from-sample {sample_set_id}` · `POST …/rows` | `sheet.edit` | rows from an approved sample; a manual row |
| `PATCH …/rows/{rid} {cells, version}` | `sheet.edit` | through `record_value`: 412 stale; 423 `row_locked` |
| `GET` · `POST` · `PATCH …/views[/{vid}]` | `sheet.read` · `sheet.edit` | saved views |
| `POST …/columns` · `PATCH …/columns/{cid}` · `GET …/columns/{cid}/usage` · `DELETE …/columns/{cid}` | `sheet.configure` · `sheet.read` | 409 `column_in_use`; 422 classification reason |
| `GET` · `PUT …/columns/{cid}/agent` | `sheet.read` · `sheet.configure` | 422 `missing_reference`; 409 `preview_required` on save |
| `POST …/agent/preview {row_ids?}` · `POST …/agent/estimate {scope}` | `agent_column.run` | preview on 3 rows writes nothing; estimate in agent-minutes |
| `POST …/agent/runs {scope, row_ids?}` · `POST …/agent/runs/{run_id}/stop` | `agent_column.run` | 409 `preview_required`, `over_budget` |
| `GET …/export.xlsx` | `sheet.export` | deterministic xlsx |

**Status words:** `sheet_cell` (F-08-T04), `agent_column`, `agent_column_run_row` (K-03-T07). **Examples (foot):** strata 24 + 16 = 40 rows; 3,286,400.00 + 412,300.00 = 3,698,700.00; conclusions Properly excluded 31 + Properly included 8 + Improperly excluded 1 + Needs input 0 = 40.
