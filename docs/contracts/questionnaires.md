# Questionnaires (v1; C5 additive v1.x)

| Field | Value |
|---|---|
| Version | v1 |
| Status | **live**; `questionnaires.v1` retired (DEC-2372) (T-02-T16 engine and templates, T-02-T22 portal routes; T-02-T35, 2026-11-01, DEC-1674); not frozen: A-04 and A-08 still add inquiry kinds |
| Provider epic | T-02 |
| Consumers | POR-05, TAX-03 drawer, A-04 and A-08 (inquiries) |
| Spec | SPEC-502 AC-5; `docs/plan/epics/T-02.md` §3, §4.3 |

## 1. Routes
| Operation | Method and path | Action |
|---|---|---|
| Import (dry run default) · list · publish a version | `POST /v1/questionnaire-templates:import` · `GET /v1/questionnaire-templates` · `POST …/{id}/versions/{v}:publish` | `questionnaire_template.import`, `.read`, `.publish` (fresh MFA) |
| Attach an organizer · create team questions or an inquiry | `POST /v1/request-lists/{id}/questionnaires` · `POST /v1/questionnaires` | `questionnaire.create` |
| Draft and send a question (person-sent) | `POST /v1/questionnaires/{id}/questions` · `POST /v1/questions/{qid}:send` | `questionnaire.ask` |
| Firm read | `GET /v1/request-lists/{id}/questionnaires` · `GET /v1/questionnaires/{id}` | `questionnaire.read` |
| POR-05 | `GET /v1/portal/questionnaires`, `/{id}?filter=&section=` | `portal_questionnaire.read` |
| Autosave (If-Match; 409 `stale_version`) · upload-if-yes | `PUT /v1/portal/questionnaires/{id}/answers/{qid}` · `POST …/questions/{qid}/attachments` | `portal_questionnaire.answer` |
| Mark done · submit and lock (addressee only) | `POST …/{id}:mark-done` · `POST …/{id}:submit` | `portal_questionnaire.complete` · `.submit` |

Templates are database content (the firm imports them); prior-year values come by code.

## 2. Status words
`questionnaire`: open · complete · submitted.

## 3. Classification
Organizer answers and prior-year values TRI; wording internal.

## Live since T-02-T16 (firm side)
The template import takes the file as the raw body (`?name=`, `?format=csv|xlsx|json`, `?dry_run=`; no multipart, DEC-1369) and answers `problems` (codes with their row) and, on a dry run, the `added`, `changed` and `removed` question keys against the current published version. Rows: `section, icon_key, key, type, client_wording, help_text, conditional_on, conditional_value`; JSON nests the same under `sections[].questions[]`. 409 `version_published`, `version_not_published`, `question_sent`, `questionnaire_closed`; 422 `template_invalid`; 413 past 2 MB. The portal routes stay stubs until T-02-T22.

## T-03 additive: questionnaires and answer effects (T-03-T02, 2026-11-03, DEC-2201)
Stub behind `questionnaires.editor` (404 off, 501 on until T-03-T05); freeze Fri Oct 29, 2027.
Additive only: no v1 route, field or status moves, so POR-05's consumers and their contract tests
are unchanged. Module: `requests/questionnaire_editor_contract.py`; slot:
`requests/answer_effect_slots.py`.

| Operation | Method and path | Action |
|---|---|---|
| A binder's organizer (BND-02 Questions tab) | `GET /v1/binders/{id}/questionnaire` | `questionnaire.read` |
| Editor read: sections, questions, follow-ups, logic, effect rules, answers, effect log, counts, `row_version`, `allowed_actions` | `GET /v1/questionnaires/{id}/editor` | `questionnaire.read` |
| Atomic save (If-Match; `?dry_run=`) | `PUT /v1/questionnaires/{id}` | `questionnaire.edit` (binder) · `questionnaire_template.draft` (template draft) |
| Client preview (the portal DTO) | `GET /v1/questionnaires/{id}/client-preview?question=&contact=` | `questionnaire.read` |
| Template detail · owner | `GET /v1/questionnaire-templates/{id}` · `PUT …/{id}/owner` | `questionnaire_template.read` · `.assign_owner` |
| Draft from current · discard a draft · diff | `POST …/{id}/versions` · `DELETE …/versions/{v}` · `GET …/versions/{v}/diff?against=` | `questionnaire_template.draft` · `.draft` · `.read` |
| Publish (owner, fresh MFA, `applies_to_tax_year`) | T-02's `POST …/versions/{v}:publish`, gaining an optional body in T-03-T05 | `questionnaire_template.publish` |

- **Errors.** `PUT`: 412 `stale_version`; 409 `question_answered` (type change on an answered question), `version_published`; 422 `client_wording_required`, `logic_invalid` (equality on a top-level yes_no or choice parent; depth 1; no cycles). Drafts: 409 `draft_exists`. Owner: 409 `owner_not_partner`.
- **Dry run.** `saved: false`, `client_visible_changes[]` (key, kind, before, after) and `effects_to_fire[]` (key, rule, kind, title); the confirm then saves.
- **Preview.** `ClientPreviewOut` is exactly POR-05's question DTO: wording, type, choices, amount parts, the Required marker, visibility and the answer. It has no `internal_helper`, effect rules, tags or banners.
- **Python API.** `requests.api.register_answer_effect(kind, handler)` (one handler per kind) and `answer_effect_handler(kind)`. An unregistered kind returns None, and the engine (T-03-T06) records `pending_handler` and leaves the upload in the binder (fail closed). `questionnaire_from_template(ctx, template_key, tax_year, binder_id)` raises 501 until T-03-T05.
- **Deviation (DEC-2201).** The editor read is `GET …/{id}/editor`, not the epic's `GET /v1/questionnaires/{id}`. That route is T-02's live v1 shape, and POR-05's TAX-03 drawer reads it.
- **Classification.** Answers are TRI. Wording, helpers and rules are internal. Contact names are confidential.
