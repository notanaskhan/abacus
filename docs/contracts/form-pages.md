# Form pages v1 — the TAX-11 draft preview

| Field | Value |
|---|---|
| Owner | tax (T-06; SPEC-702) |
| Status | v1 live (T-06-T44, 2026-11-23; DEC-5915); stub T-06-T07 (DEC-5516) |
| Code | `backend/src/abacus/modules/tax/entity_depth_contract.py` (`entity_depth_router`) |
| Flag | `tax.form_preview` (default off; off: 404) |
| Fixtures | `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/entity_depth_slice.py` |
| Consumer tests | `backend/tests/contracts/t06_entity_depth/` and `apps/web/src/fixtures/contracts/t06-entity-depth.contract.test.ts` (T-06-T09) |

Every figure is TRI (`restricted`, `tri=True`): agents read it only with §7216 use and ai_disclosure in force (C19); nothing reaches the portal (INV-4). Client 404 → flag 404 → human-only 403.

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/tax-returns/{id}/form-pages?checkpoint=` | `form_preview.read` | from the named or the newest approved checkpoint; "Draft — not for filing"; 409 `form_template_missing` (no published `tax_form_face` for the form and tax year), 409 `checkpoint_required` |
| `GET …/form-pages/{page_key}/image` | `form_preview.read` | the page as `image/png`, rasterised from the same PDF in the isolated child; `no-store` |
| `GET …/form-pages/{page_key}/fields` · `GET …/fields/{field_key}/trace` | `form_preview.read` | field manifest; SHL-09 trace |
| `GET …/diagnostics` | `form_preview.read` | each linked to an existing issue by `rule_key` |
| `GET …/k1-previews` | `k1_package.read` | Σ box 2 = Schedule K line 2 |
| `POST …/form-pages:download-draft` | `form_preview.download_draft` | fresh MFA; audited (DEC-60); no transmit |

**Example:** Σ box 2 24,632 + 468,008 + 400,270 + 30,790 + 307,900 = 1,231,600 = Schedule K line 2. Final approval refuses 409 `blocking_diagnostics` while any blocks (T-06-T37). 
**Values (T-06-T44).** Code resolves each manifest field from its binding: `workbook_cell` reads the cell at the checkpoint; `tb_line` sums sheet 03's signed nets under the form-lines key (a credit-side line printed negated), and `L14` / `L22` are code's totals of the reference set's sides (assets less contra assets; liabilities and capital); `return_fact` reads `entity.name`, `entity.ein` (masked `••-•••1234`, none for an offshore reader; the full TIN never leaves the sealed store), `return.k1_count`, the profile's activity and business code, Analysis of Net Income (code's sum over 06 and 09 by partner kind) and the approved engine summary's page-one lines (`1065.1a`), Schedule B answers (`1065.B3`) and items B and E (`1065.item_b`, `1065.item_e`). A fact no source carries prints blank. Money prints whole dollars with separators, negatives in parentheses. The mask is burned into the page text, not a layer.

**Renders.** The PDF is C11's form-face renderer (`reporting.api.render_face`, C11 v1.2): the same checkpoint and template version give the same bytes (dates from the checkpoint's recorded time, identifier from the content hash over checkpoint, template version and every field's value). `form_page_renders` keeps one `ready` row per (checkpoint, template version, page) with that hash; a second render of the pair adds nothing.

## Attached forms and placeholders (T-06-T49, DEC-6023)

- `GET …/form-pages` lists the face's pages, then the return's attached forms in TAX-11's order. For a 1065 these are Form 8825, Form 4562, then Schedule M-3, Schedule C (M-3 filers) and Form 8916-A once total assets reach 10,000,000, then the §199A statement, then the §754 statement once an interest was transferred. Each attached form is the firm's published `tax_form_face` for that form and year (form keys `8825`, `4562`, `1065-m3`, `1065-m3-c`, `8916-a`, `1065-199a`, `1065-754`). Its page and field keys are prefixed with the form, e.g. `f8825_p1` and `f8825_p1_name`.
- **Placeholder** (additive `placeholder: true`): an attached form with no published template is listed as one page under TAX-11's caption ("Form 4562", "§199A stmt"). TAX-11 shows the placeholder thumbnail and page, never a blank. A placeholder has no fields (`/fields` 404) and no image (`/image` 404), and it is never cached, rendered or in the draft PDF.
- **Audit**: the first render of a page writes its `form_page_renders` row and one `form_preview.rendered` event. A read of pages already rendered writes nothing. Before this, a first read failed on the database because it wrote with no audit event.
- **Content**: TY2025 and TY2028 drafts of the M-3 (pages 1–3), 8825, 4562 (summary page), §199A and §754 statement faces are outside the repository and load through `python -m abacus_tools.form_faces` (T-06-T43's loader).
