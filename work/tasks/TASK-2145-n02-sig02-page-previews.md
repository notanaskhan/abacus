---
id: TASK-2145
title: SIG-02 page previews (N-02-T20 follow-up)
spec: SPEC-381
acceptance_criteria: [AC-1]  # the follow-up's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T20
branch: s16-sig02-previews
created: 2026-10-30
updated: 2026-10-30
---

## Objective
`GET /v1/envelopes/{id}/documents/{doc}/pages/{n}` was still a 501 stub after N-02-T20 and
N-02-T21. Acceptance: an envelope document's page is served as the evidence viewer's masked PNG,
`no-store` and `nosniff`, logged as a content read; another envelope's document is 404, a
generated document 409 `preview_unavailable`, a walled person 404.

## Plan
- `signatures.builder.document_page`: the envelope visible to the person, the document on that
  envelope, then `evidence.api.viewer_page` (its own `evidence.read` check, the offshore refusal,
  `preview_outdated`, the access event). A generated document (P-11) has no preview: 409.
- Route `envelope_page_route` live (errors 409); C7 contract test lists it live.
- Error catalogue and generated client regenerated.
- Test: `backend/tests/integration/backfill/test_n02t20_page_previews.py`.

## Progress log
- 2026-10-30: built; previews test (4) and C7 contract tests pass.
