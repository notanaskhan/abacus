# Questionnaires (v1; C5 additive v1.x)

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-02-T02, 2026-10-29): every route 501 behind `questionnaires.v1` |
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
