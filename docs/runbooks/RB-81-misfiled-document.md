---
id: RB-81
title: Misfiled document correction (intake filed to the wrong place)
owner: builder
owning_epic: N-01
alarms: []
last_rehearsed: never
rehearse_by: 2027-06-25
---
# RB-81 · Misfiled document correction

| Field | Value |
|---|---|
| Owner | builder (N-01-T30); the firm's preparer does the correction |
| Severity range | SEV4; SEV2 if it was filed to another client's engagement (then RB-08 first) |
| Linked from | `backend/src/abacus/modules/evidence/README.md` (Intake sources, classification and Files) |
| SLO affected | none |
| Kill switches that apply | none |
| Related | RB-08 (cross-firm exposure), RB-32 (withdrawal and erase), RB-14 (legal holds) |

Evidence is immutable (ADR-004): nothing is moved or deleted. A wrong filing is corrected by
returning it and filing the right document, so the record shows both (N-01 OQ-5).

## 1. Recognise it
A preparer or reviewer sees a document on the wrong request, the wrong work item, or the wrong
year; or a client says "that is not the file I sent".

## 2. Contain
- **Another client's engagement?** Treat as exposure: RB-08 §1–3 before anything else. Who could
  read it is in the Files drawer's access log (FIL-01).
- Otherwise nothing to contain.

## 3. Preserve
Note the evidence item and version ids and the triage decision (`GET /v1/inbox/messages/{id}/triage`
shows who filed it). Never copy the file.

## 4. Assess
- Filed to a **request** that it does not answer: §6.1.
- Filed to the client's **permanent file** or a work-item folder by mistake: §6.2.
- A **superseded** version was the right one: the struck version is kept; file it again as §6.1.

## 5. Notify
The engagement's preparer and, when §2 applied, the firm's security admin.

## 6. Recover
1. **Wrong request:** Return it with reason `wrong_document`
   (`POST /v1/engagements/{e}/request-items/{id}/return-to-client`); the client sees the
   firm's note. The right file goes in by upload on behalf on the right request
   (`POST …/request-items/{id}/uploads`) or arrives again through the Inbox.
2. **Wrong folder:** the document stays where it is (insert-only). Upload the right copy on behalf
   where it belongs. N-01 has no way to mark the wrong copy as not relied on: record the
   correction where the engagement's team keeps its review comments.
3. Never re-file a Filed attachment from the Inbox (not in N-01; the FIL-01 writes follow-on adds
   a reference-only "File again…").

## 7. Verify
The request shows Returned with the reason, the right document is on the right request, and the
item's access log shows the correction.

## 8. Review
If the matcher proposed the wrong destination and a person accepted it, the shadow score records it
(`triage_outcomes`); a recurring pattern goes to the matcher's eval set (N-01-T26).

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
