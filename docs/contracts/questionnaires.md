# Questionnaires (v1; C5 additive v1.x)

| Field | Value |
|---|---|
| Version | v1 |
| Status | **live** behind `questionnaires.v1` (T-02-T16 engine and templates, T-02-T22 portal routes; T-02-T35, 2026-11-01, DEC-1674); not frozen: A-04 and A-08 still add inquiry kinds |
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
