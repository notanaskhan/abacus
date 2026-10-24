---
id: TASK-1183
title: C5 v1.1 additive fields on P-06's binder-requests projection, the Source Documents aggregate and requests.api.pbc_counts (A-01-T10)
spec: SPEC-330
acceptance_criteria: [AC-25, AC-26, AC-27]
risk_zone: amber
status: done
epic: A-01
plan_key: A-01-T10
branch: s8a-audits-read
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Northwind returns 24 rows grouped 5/6/7/4/1/1 with owed-by, match confidence and Linked (n), and P-06's consumer tests stay green."

## Plan (amber zone)
- **requests:** `source_documents.py`: `row_facts` (owed by: an open delegation's contact, else the client assignee; the newest live fulfilment as the latest upload; Linked (n) = live fulfilments), `pbc_counts`, `source_documents` (across the work item's published PBC binders, by category in binder order, Missing first or Received first, `q`). A slot `register_upload_facts` for what requests cannot read itself (the upload's path label, uploader kind and the matcher's confidence), registered by evidence (`evidence/upload_facts.py`: the evidence item's title, the version's source, the inbox file's matcher pick through the registered match picks). `binders.binder_requests` fills the three C5 v1.1 fields and `linked_count`; `for_viewer` still drops them for a client.
- **assurance:** `GET /v1/audits/{id}/source-documents` live behind `audits.cockpit`.
- **Tests:** `tests/integration/test_c5_v11_fields.py` (AC-25 to AC-27, client principal never sees the fields); P-06's consumer tests unchanged.
- **Deferred:** the screening glyph stays P-06's (SHL-20, P-06-T15): `screening` is not filled here.
- **Rollback:** revert; the fields read null again.

## Progress log
- 2026-10-25: built. `requests/source_documents.py` (row facts, `pbc_counts`, `pbc_counts_of`, `source_documents`), evidence's `upload_facts` provider through `requests.api.register_upload_facts`, `binders.binder_requests` fills `owed_by`, `latest_upload`, `match_confidence`, `linked_count` for firm readers; `for_viewer` still drops them for a client. Northwind at E0: 24 rows grouped 5/6/7/4/1/1, 11 received; Dana's rows read `client_contact`. Live owed-by for Harborline, PayGrid and Keystone is null (no organisation or delegation is stored in the E0 slice), and Linked (n)/match confidence are null at E0 (the slice seeds no fulfilments); both proven on seeded data in `test_audits_read_models.py`. Screening stays P-06-T15's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-313 | Owed-by, latest upload, match confidence and Linked (n) rules; pbc counts | No |
