# C11 Renderer and templates (v1 draft)

| Field | Value |
|---|---|
| Register row | C11 |
| Version | v1 |
| Status | stub (P-11-T03, 2026-10-29): every route 404 for a client principal, then its matrix action, then 404 with `reporting.generated_documents` off and 501 with it on until P-11-T06 (templates) and T11 (generated documents). **Templates live (P-11-T06, 2026-10-30):** list, version, import and publish answer from `reporting/templates.py` and methodology's tables (0460); the SAMPLE preview waits for P-11-T07. Fixture mode serves the shapes from the Brightwater Hale seed (`apps/web/src/fixtures/handlers/reporting.ts`) |
| Provider epic | P-11 |
| Consumers | N-02 (ENG-04 letters, §7216 consent documents), A-07 (AUD-20…23), T-01/T-02 (TAX-12 delivery cover letter), N-04 (NOT-03), C-01/C-02 (CLS-08), A-10 (FSP-06), P-10 (trace.pdf, P-10-T44), F-06 (T10 `DocumentVM`), F-07 (field manifest), T-06 (form-face previews) |
| Freeze sprint | S18 Contract Monday (Mon Jun 28, 2027) |
| Flags | `reporting.generated_documents` (per firm, default off) |
| Spec | SPEC-520; `docs/plan/epics/P-11.md` §4, §8.1 |
| ADRs | ADR-320 (P-19, deterministic document generation), ADR-321 (P-32, OCR; part 2), ADR-042, ADR-110 |

## 1. Purpose
One renderer for every document the platform produces: templates are database rows of DocBlocks,
renders are deterministic PDF and DOCX through code-owned layouts, and every rendered file is an
evidence version. Consumers register a document kind, ask for drafts, and ask for a final render
only with a human approval.

## 2. Callers and actions
| Operation | Method and path | Matrix action | Agent / system |
|---|---|---|---|
| Template list | `GET /v1/report-templates?family=` | `report_template.read` | deny |
| Template version | `GET /v1/report-templates/{id}/versions/{n}` | `report_template.read` | deny |
| Template import (dry run or draft) | `POST /v1/report-templates/import?dry_run=` | `report_template.import` | deny |
| Template publish (fresh MFA) | `POST /v1/report-templates/{id}/versions/{n}/publish` | `report_template.publish` | deny |
| Template SAMPLE preview | `POST /v1/report-templates/{id}/versions/{n}/preview` | `report_template.read` | deny |
| Generated document | `GET /v1/generated-documents/{id}` | `generated_document.read` | agent: `task_scope` |
| Field regions | `GET /v1/generated-documents/{id}/versions/{n}/fields` | `generated_document.read` | agent: `task_scope` |
| Compare | `GET /v1/generated-documents/{id}/versions/{n}/compare?to=standard\|{m}` | `generated_document.read` | agent: `task_scope` |
| Changes since snapshot | `GET /v1/generated-documents/{id}/changes` | `generated_document.read` | agent: `task_scope` |
| Regenerate (Idempotency-Key) | `POST /v1/generated-documents/{id}/regenerate` | `generated_document.regenerate` | deny |
| Pages, download | P-03's `GET /v1/evidence-versions/{v}/viewer`, `/pages/{n}` and the audited content route | `evidence.read` | as C4 |

In-process (`reporting.api`, inside the caller's unit of work): `register_document_kind(kind,
layout, variables_provider, approval_provider, source_events, retention_record_type)`,
`render(tx, RenderRequest) → RenderTicket`, `render_final(tx, document_id, approval_ref)`,
`lock(tx, document_id, cause_ref)`, `generated_document(tx, id)`. Values are resolved by the kind's
provider from the database; a consumer never passes values from the browser.

## 3. Status words
`generated_document` (C2, DF-31): Drafting · Draft · Approved · Locked, with the Out of date
overlay. Computed from the latest version and events; never a stored mutable column.

## 4. Human-only actions
`report_template.import`, `report_template.publish` (fresh MFA; a different person from the
importer), `generated_document.regenerate`, and every final render (`mode=final` requires a human
`approval_ref` whose `content_hash` matches). An agent requests drafts only.

## 5. Audit events
`report_template.imported` · `report_template.published` · `report_template.deprecated` ·
`generated_document.rendered` · `generated_document.finalised` · `generated_document.regenerated` ·
`generated_document.locked` · `generated_document.marked_out_of_date` (changed keys, never values).

## 6. Shapes (v1)
| Part | Shape |
|---|---|
| `RenderRequest` (in-process) | `{kind, owner_ref{type, id}, scope{client_id, engagement_id?, work_item_id?}, template_version_id, clause_states[{clause_id, enabled}], section_overrides[{section_id, paragraphs[], authored_by_user_id}], mode: draft \| final, formats[pdf \| docx], approval_ref?{kind, id, content_hash}, requested_by}` |
| `RenderTicket` | `{generated_document_id, version_no, status: drafting}` |
| `GeneratedDocumentOut` | `{id, kind, owner_ref, status, out_of_date, out_of_date_reasons, current_version, versions[…], allowed_actions}` (P-11 §4.3) |
| `FieldRegion` | `{field_key, label, page, rect_pt[x0, top, x1, bottom], value_text, match_id}` |
| `DocBlock` | closed union: `section`, `heading`, `paragraph {runs: [text \| var \| cite]}`, `clause`, `list`, `table` (decimal strings), `kv`, `signature_block`, `legend`, `image {asset_id}`, `enclosures`, `page_break` |
| `ReportTemplateOut`, `ImportReport` | P-11 §4.3 |

## 7. Errors
404 invisible or walled · 403 role · 409 `document_locked` · `approval_hash_mismatch` ·
`already_published` · 422 `missing_variable{keys}` · `final_requires_approval` ·
`markup_not_allowed` · `unknown_variable` · `asset_not_allowed` · `missing_glyph` · 503
`renderer_unavailable`.

## 8. Stub
`backend/src/abacus/modules/reporting/contract.py` (models and routes) and `reporting/api.py`
(the in-process shapes, `register_document_kind`, `check_render_request`; `render`,
`render_final` and `lock` raise until P-11-T08); matrix `docs/architecture/permission-matrix/reporting.yaml`;
flag `docs/architecture/feature-flags/reporting.yaml`; fixtures
`apps/web/src/fixtures/handlers/reporting.ts`. Stub tests:
`backend/tests/contracts/c11_renderer/test_c11_stubs.py`; consumer suite
`backend/tests/contracts/c11_renderer/test_c11_consumer.py` and
`apps/web/src/fixtures/contracts/c11-renderer.contract.test.ts` (P-11-T04).

## 9. Versioning
Additive changes in place (DOCX if descoped, T-06's diagnostic field). A breaking change is C11 v2
with one sprint of overlap.
