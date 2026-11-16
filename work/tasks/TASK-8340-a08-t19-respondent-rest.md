---
id: TASK-8340
title: "A-08-T19: Respondent path, the rest: the live open view, scanned attachments, the access record and the account list"
spec: SPEC-657
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
branch: a08-t19-respondent-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T19
---

## Objective
Spec section: SPEC-657 F5 (AC-7.1 to AC-7.6). Respondent path, the rest: the live open view, scanned attachments, the access record and the account list.

## Plan (red)
1. `confirmations_service.respondent_view_of`: `answered` once the one answer is in; `open` with this confirmation's render data (reference, type, firm, client, respondent's organisation, the fiscal year end, the client's authorization in the handoff's POR-17 words, who signed it and when, the balance or the bank's account lines) only while Sent under a completed authorization; else the uniform expired view.
2. Send of an Accrued-link confirmation needs a completed client authorization (409 `authorization_missing`, as the route promised).
3. `POST /v1/confirm/{token}/attachments`: the raw body, refused past the upload limit; scanned and typed before storage (`evidence.api.file_respondent_copy`: correspondence on the engagement, channel `confirmation_response`, Object Lock as a client document); 0932's `confirmation_attachments`; the answer may cite only its own link's files (422 `attachment_invalid`).
4. 0932: `confirmation_responses` gains `ip_sealed`, `user_agent` (the P-14 access record) and `accounts` (the bank variant's list).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5325). Lint, pyright clean; the app imports; client regenerated. Partial: POR-17's front end (the respondent's page) is still planned. Gates and
  tests run once at the S47 end pass (build first, test last).
