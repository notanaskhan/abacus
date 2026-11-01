# Tax-engine bridge (v1)

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-01-T02, 2026-10-29): every route 501 behind its flag |
| Provider epic | T-01 |
| Consumers | T-02 (TAX-02 sync chip, status machine), P-04 (SHL-12 h final approval), T-08, W-01 |
| Flags | `tax.engine_bridge` |
| Spec | SPEC-501 AC-5 to AC-8; `docs/plan/epics/T-01.md` §3.7–§3.10, §4.3 |
| ADRs | ADR-231 (the engine of record computes), ADR-052 (hostile engine files), ADR-040 (connectors read; W2 is a file the firm carries) |

## 1. Purpose
CCH Axcess Tax is the engine of record; the link is a **file bridge** (W2 `cch_axcess_tax.export_file`, mode `file`, no egress host). Accrued exports a workbook only after final approval and imports engine files through a diff a person approves.

## 2. Routes
| Operation | Method and path | Action |
|---|---|---|
| Final-approval facts and blockers | `GET /v1/tax-returns/{id}/final-approval` | `tax_return.read` |
| Final approval (L4 `final_approval` sign-off; only `tax/approval.py`) | `POST /v1/tax-returns/{id}/final-approval` `{seen_checkpoint_id, content_hash}` | `tax_return.approve` (`function_in(signer)`; BH-TAX-02's approver in the service) |
| Sync chip, history, diagnostics | `GET /v1/tax-returns/{id}/engine-sync` | `tax_return.read` |
| Export (consumes the write grant) | `POST /v1/tax-returns/{id}/engine-exports` | `tax_return.export` |
| Audited download · a person marks it exported | `GET /v1/engine-exports/{id}/file` · `POST …/mark-exported` | `tax_return.export` |
| Upload an engine file (`values`, `diagnostics`, `pdfs`, `acks`): the file is the raw body, `?kind=`, `X-File-Name` (no multipart; T-01-T19, DEC-1363) | `POST /v1/tax-returns/{id}/engine-imports` | `engine_import.create` |
| Diff · approve · reject | `GET /v1/engine-imports/{id}` · `POST …/approve` · `POST …/reject` | `tax_return.read` · `engine_import.approve` |
| Settings (locked cells), mappings (409 `mapping_conflict`), format check | `GET`/`PUT /v1/firm/integrations/{key}/settings`, `PUT …/user-mapping`, `…/office-mapping`, `…/status-mirror`, `POST …/test` | `integration.read`, `integration.configure` (fresh MFA), `integration.test` |

## 3. Sync-chip states
not_yet_exported · ready_for_export · exporting · synced · out_of_sync · import_pending_approval · failed (the registry's `return_sync_chip`).

## 4. Module API
`tax.api.final_approval_blockers(return_id)`, `tax.api.register_final_approval_blocker(kind, provider)` (T-02 registers the draft K-1 blocker); raise until T-01-T27.

## 5. Events
Outbox: `tax_return.approved`, `engine_sync.exported`, `engine_sync.failed`, `engine_sync.imported`, `engine_import.pending_approval` (identifiers and counts only). Audit: `return.final_approved`, `engine_export.generated`, `.downloaded`, `.marked_exported`, `engine_import.uploaded`, `.approved`, `.rejected`, `engine.diagnostic_received`, `integration.settings_updated`, `.mapping_updated`, `.tested`.

## 6. Engine files (file mode; T-01-T22)
What staff carry between Accrued and CCH Axcess. `abacus_tools/fakes/cch_axcess.py` emits these from Accrued's export in synthetic environments; `conformance(name, bytes)` is the check the adapter's suite runs on the fake's files and on the partner-validated samples (F-09-T120) once filed. Engine return id: `<tax-year><type>:<client-code>:V<n>` (`2025I:FeldJ:V3`).

| File | Format | Columns or content |
|---|---|---|
| Export workbook (Accrued → engine; built by T-01-T25) | `.xlsx` | Sheet `Return`: key/value rows `return_id`, `tax_year`, `form`. Sheet `Fields`: `field_key`, `form`, `line`, `value` |
| Values (`values`) | CSV, UTF-8, `\n` | `return_id, version, field_key, form, line, value`; `version` reads `V<n>` |
| Diagnostics (`diagnostics`) | CSV | `return_id, version, severity, code, form, field_key, message`; severity `error`, `warning` or `informational` |
| PDFs (`pdfs`) | PDF | One file per kind: client copy, Form 8879, NY TR-579-IT, next year's 1040-ES and IT-2105 vouchers, K-1; named `<engine id with _>_<kind>.pdf` |
| E-file status report (`acks`) | CSV | `return_id, jurisdiction, submission_last4, status, status_at, reject_code, reject_text`; status `accepted` or `rejected`, a rejection carries its code; the submission id is never stored beyond its last four |

## 7. Live since T-01-T19
The engine-sync read, the values and diagnostics imports, the import read and its approve and reject are live behind `tax.engine_bridge`. 409 `engine_return_mismatch`, `engine_version_behind`, `import_pending`, `import_decided`, `stale_version`; 422 `engine_file_invalid` (`facts.reason`, never the file's content), `import_kind_unavailable` (PDFs and acks land with T-01-T26 and T-01-T27), `nothing_accepted`; 413 past 10 MB.

## 8. ADM-08 settings, live since T-01-T20
Cells (stored as `integration_mappings`): `return_id_template` (default `{Tax year}{Type}:{Client code}:V{n}`; must keep `{Tax year}`, `{Client code}` and end `:V{n}`), `client_code_rule`, `type_letter.<form>`, `who_may_export` (`reviewer_manager_signer`, `manager_signer` or `signer`: narrower only), and the locked `export_after_final_approval`, `import_requires_approval` (`stricter_only`) and `status_push` (`file_mode_has_no_push`). Mappings replace the kind's rows; `workflow_status` keys are return status codes. Every save carries the install's `version`. 409 `setting_locked`, `mapping_conflict`, `stale_version`; 422 `setting_invalid`. `POST …/test` returns codes only (`no_engine_file`, `check_failed`, or the holder's) and `returns_read` (additive).

## 9. Export, live since T-01-T25 (DEC-1462)
`POST /v1/tax-returns/{id}/engine-exports` `{checkpoint_id}` consumes the final approval's grant (identity's `consume_grant`, bound to the checkpoint's content hash) and answers 201 with the export; the same checkpoint answers the same export (one per checkpoint, identical bytes). `GET /v1/engine-exports/{id}/file` is the workbook, fingerprint-checked and audited `engine_export.downloaded`. `POST …/mark-exported` `{seen_version}` is a person's, once; the chip then reads Synced. `EngineExportOut.version` (additive). 409 `export_disabled` (`facts.switch`: `capability` while the W2 registry entry is disabled, `firm` while the file-bridge install is not connected), `not_final_approved`, `grant_refused`, `undo_window_open`, `already_marked`, `stale_version`. Each export writes one `write_operations` row (one per grant) and an `export_generated` sync event; `engine_export.generated` and `.marked_exported` are human-only audit actions (0561).

## 10. PDFs, acknowledgements and diagnostic issues, live since T-01-T26 (DEC-1464)
`kind=pdfs` (one PDF per upload, named `<tax year><type>_<client code>_V<n>_<kind>.pdf`, kinds as in §6) files an imported evidence version (channel `import`, source `engine_import`): the client copy, vouchers and K-1s in Deliverables, Form 8879 and NY TR-579-IT in Signed authorizations. `kind=acks` stores one pending `engine_acks` row per jurisdiction (`federal` or a state's two letters; the submission id's last four only) and announces `engine_ack.rejected` per rejection. A diagnostics `error` raises one `engine_diagnostic` issue per return and `engine:<code>:<field>` however often the file is re-imported. Both answer 201 with an import of status `routed`. 422 `engine_file_invalid` reasons add `bad_pdf_name`, `unknown_pdf_kind`, `not_a_pdf`; `import_kind_unavailable` is no longer answered.

## T-01-T33 additions (DEC-1473)
`EngineSyncOut.checkpoint_id` (additive): the return's current checkpoint, the one `POST …/engine-exports` requires. The live read fills `blockers` (`final_approval_required` first until the return's status is exportable, then final approval's blockers) and `approver_name`.

## T-01-T51 additions (DEC-1667)
Additive: `EngineSettingsOut.last_sync_return_id` (default null): the return of the firm's latest sync (an approved import or a marked export), which ADM-08's Last sync opens as TAX-09 (`?ov=engine-sync:<id>`; TAX-09 authorises the return itself). Integrations never reads tax: tax answers through `integrations.api.register_last_engine_sync`. TAX-12 is routed at `/tax-returns/$returnId/delivery` behind `tax.returns_v1` and `tax.delivery_efile`.
