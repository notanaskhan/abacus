# BND-03 · Questionnaire editor

| Field | Value |
|---|---|
| Route and params | `/binders/questionnaires/$questionnaireId` · `?section=<key>` `?q=<key>` `?edit=1` · `?ov=client-preview` · `?ov=save-confirm`; template mode `/knowledge/organizers/$templateId` · `?version=<n>` · `?ov=publish-organizer:<templateId>:<v>` |
| Template and host frame | T2 RecordCockpit with the dock slot (F-05-T40) · `Wave 3 - Engagements & Projects.dc.html#bnd03` |
| Surface | firm; the dock renders the portal's own question renderer (no firm internals) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/BND-03 Questionnaire editor/` (README.md, spec.md; no revision.md) |
| Epic and tasks | T-03 · stubs T02 (`docs/contracts/questionnaires.md` §T-03 additive) · service T05 · effects T06 · a, e and the dock T09 · b, c, d T10 · E2E and parity T17 |
| Manifest status | planned until T-03-T09 (fixture) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | kevin-osei | Mon Sep 14, 2026, 9:24 AM CT | Feld 2025 Binder Published; v6 organizer; 8 of 9 answered; effects: request "estimated payment confirmations", review point on Q2 | fixture (T09) |
| b | kevin-osei | same | a + Q5 in edit mode; follow-up 2 Required on (unsaved); "Show when Q5 = Yes"; sticky Save bar | fixture (T10) |
| c | kevin-osei | same | a + a new empty card at the end of Payments & refunds, the type picker open | fixture (T10) |
| d | kevin-osei | same | Template 1040 organizer v6 (Draft v7 open), no answers, Phone preview; banner "Editing template 1040 organizer v6 — changes apply to TY2026 binders" | fixture (T10) |
| e | kevin-osei | same | a + section Health coverage with 0 questions: "No questions in this section." | fixture (T09) |
| composed | as a | — | Save confirm (dry run list), 412 reload, Publish… ConfirmDialog with step-up, flag off and not allowed (C-20) | composed (DEC-32) |

## API
| Read or write | Endpoint | Shape | Matrix action | Notes |
|---|---|---|---|---|
| read | `GET /v1/binders/{id}/questionnaire` | `BinderQuestionnaireOut` | `questionnaire.read` | BND-02 tab badge |
| read | `GET /v1/questionnaires/{id}/editor` | `QuestionnaireEditorOut` | `questionnaire.read` | — |
| write | `PUT /v1/questionnaires/{id}?dry_run=` | `QuestionnaireSaveOut` | `questionnaire.edit` · `questionnaire_template.draft` | If-Match; 412, 409, 422 |
| read | `GET /v1/questionnaires/{id}/client-preview` | `ClientPreviewOut` | `questionnaire.read` | the portal DTO |
| write | `POST /v1/questionnaire-templates/{id}/versions` · `DELETE …/versions/{v}` | `OrganizerTemplateVersionOut` | `questionnaire_template.draft` | 409 `draft_exists` |
| write | `POST …/versions/{v}:publish` | T-02's | `questionnaire_template.publish` | owner, fresh MFA |

## Status
`questionnaire_template_version`, `answer_effect` (the Logic band).

## Copy
Verbatim from spec.md: "Questionnaire", "Sections", "Logic", "Questions", "Reorder", "Preview as client", "+ Question", "Client preview", "Desktop", "Phone", "Unsaved changes", "Discard", "Save", "Show when", "Write the question as the client will read it", "No questions in this section.", the helpers and banners of state a.

## Deviations
- DV-BND-03-1 (DEC-2201): the banner's "open in TAX-06" is a **planned** link. Until T-04 it opens TAX-02's issue anchor.
- DV-BND-03-2: the organizer template route is `/knowledge/organizers/$templateId` (Knowledge active), as the epic's one-line addition to chapter 04.
- DV-BND-03-3: the editor read is `GET …/{id}/editor`, because T-02's `GET /v1/questionnaires/{id}` keeps its v1 shape.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Tab row Requests / Questions / Activity (request 7) | BND-02 | live |
| Return intake | TAX-03 | live |
| Preview as the client sees it (1400) | POR-05 | live |
| Review point | TAX-02 | live |
| Return issues | TAX-06 | planned |
| Program editor · 1040 organizer v6 | KNW-03 | live |
| Routed uploads (Q8) | NOT-01 | live |
