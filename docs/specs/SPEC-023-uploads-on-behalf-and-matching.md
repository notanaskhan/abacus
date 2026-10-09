---
id: SPEC-023
title: Uploads on the client's behalf, bulk upload and matching
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-047, ADR-052, ADR-104]
related_specs: [SPEC-004, SPEC-020, SPEC-021, SPEC-022]
created: 2026-10-09
updated: 2026-10-09
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
The rest of Phase 2 increment 6 that can be built before staging. Three parts:
- **Uploads on the client's behalf:** a firm team member uploads a file the client sent another way (for example by email), recorded as received from the client by that team member.
- **Bulk upload:** the client, or the team on their behalf, drops several files at the engagement level, not item by item.
- **Matching:** each bulk file gets suggested request items by rules over its file name. A person confirms or changes each match before anything is linked (ADR-005: the platform proposes, people decide).

## 2. Problem and context
- **Uploads are client-only and per item (SPEC-020).** Clients often send a batch of files at once, by email or in a shared folder, and the team has to put each on the right request.
- **Two parts of increment 6 must wait:**
  - **email reply matching** needs inbound email (staging, TASK-014);
  - **screening uploaded files** means opening them, which waits for malware scanning (SPEC-020 Q7) (Q4).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement team (partner, manager, senior, staff) | Upload on the client's behalf; confirm matches |
| Client admin | Bulk upload; confirm their own matches |
| Client contributor | Bulk upload limited to their assigned items (matches only among those) |

## 4. Goals and non-goals
**Goals**
- **Uploads on behalf:**
  - the team gets "Upload for the client" on the item page and the Board, using the SPEC-020 upload path and checks;
  - provenance is `uploaded` with source `firm_upload_for_client`, the uploader is the team member, and an optional note says where it came from (for example "emailed by the controller on 3 Oct");
  - the client sees it in their upload history as "Added by your auditor".
- **Bulk upload:**
  - `POST /v1/engagements/{id}/inbox` (`evidence.upload` on the engagement) accepts files one per request with the same checks as SPEC-020 (25 MB, type by content);
  - each file is stored once and becomes an **inbox file**, not yet evidence for any item.
- **Matching (rules, Q2):**
  - each inbox file gets up to three suggested items, scored by overlapping words between the cleaned file name and the item's description and area, plus tier and dataset hints (for example "TB" or "trial balance" points to the trial balance item);
  - suggestions are proposals, shown with their score and the words that matched.
- **Confirming:**
  - `POST …/inbox/{file_id}/assign` with an item ID, by a person allowed `evidence.upload` on that item, creates the evidence version (as SPEC-020 does), links it, marks the item received and audits the decision, including whether it followed a suggestion;
  - `POST …/inbox/{file_id}/discard` removes it from the inbox. The stored bytes stay (write-once storage), but the file is no longer listed.
- **Screens:**
  - an Inbox panel in the client portal and on the firm Requests board: files, suggestions, assign (a picker), discard;
  - the counter shows how many files are unassigned.

**Non-goals**
- Email reply matching (staging) (Q4).
- Opening, previewing or screening uploaded files (malware scanning first) (Q4).
- A model matcher (Q3).
- Splitting one file across several items.

## 5. User stories and acceptance criteria
- **AC-1** Given a team member allowed `evidence.upload`, when they upload for the client on an item, then a new version is stored with source `firm_upload_for_client`, the uploader and the optional note, the item is received and audited, and the client sees "Added by your auditor".
- **AC-2** Given a client admin, client contributor or team member, when they drop files into the inbox, then each allowed file is stored and listed as unassigned with up to three suggestions. Refused files (size, type, duplicate in the inbox) show the SPEC-020 messages.
- **AC-3** Given a suggestion, then it shows its score and matched words. A contributor only ever sees suggestions among items assigned to them.
- **AC-4** Given an inbox file, when a permitted person assigns it to an item, then it becomes evidence on that item as in SPEC-020, the decision is audited (followed a suggestion or not), and the file leaves the inbox. Assigning to an item that no longer takes evidence is refused.
- **AC-5** Given an inbox file, when it's discarded, then it leaves the inbox, the discard is audited, and nothing becomes evidence.
- **AC-6** Given every new screen, then loading, empty ("Nothing waiting to be matched"), error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. The client drops 6 files into the inbox.
2. Each one is stored and suggestions are computed.
3. The client or the team assigns each file, which creates the evidence version and links it.
4. Screening of uploads waits for scanning (Q4).

## 7. Domain and data changes
`inbox_files` (in the evidence module):
- engagement, file name (cleaned), media type, size, fingerprint, the stored object, uploaded by, note;
- status: `waiting`, `assigned` or `discarded`;
- assigned item and assigned version.

It's tenant-scoped with forced RLS. Inserts and status changes go through the unit of work.

## 8. Interfaces
- `POST /v1/engagements/{id}/request-items/{item_id}/uploads?on_behalf=true&note=…` (extends SPEC-020)
- `POST /v1/engagements/{id}/inbox`
- `GET …/inbox`
- `POST …/inbox/{file_id}/assign`
- `POST …/inbox/{file_id}/discard`

## 9. Authorisation and tenancy
- **Bulk upload:** `evidence.upload` on the engagement. For contributors, the inbox shows only their own files, and they can assign only to their assigned items (item facts, SPEC-020).
- **Assign:** `evidence.upload` with the target item's facts.
- **Discard:** the uploader, or a team member allowed `evidence.upload`.

## 10. AI behaviour
None. Matching is rules over file names (Q2, Q3).

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **The same file twice into the inbox:** refused as a duplicate.
- **Assigning a file that's already on the item:** refused, as SPEC-020 does.
- **An unhelpful file name** ("scan0001.pdf"): no suggestions, so the person picks the item.
- **A client admin assigns to an item hidden from the client:** not offered and refused.

## 13. Security and privacy
- **No content is read:** files are never opened, and matching reads the cleaned file name only.
- **Plain text only:** names and notes are shown as text.
- **Write-once storage:** discarded files stay in the evidence store and are no longer listed (ADR-016). Their retention follows the store's.

## 14. Audit trail and evidence integrity
`inbox_file.added`, `inbox_file.assigned` (with `followed_suggestion` 0/1) and `inbox_file.discarded`, plus the SPEC-020 events on assignment.

## 15. Observability
Inbox size, time to assign, and the share of assignments that followed the top suggestion. This is the baseline the model matcher must beat (Q3).

## 16. Performance and scale
Batches of up to 50 files. Suggestions are computed on upload, against up to 2,000 items.

## 17. UX
- **Inbox panel:** a drop zone plus a list of files. Each has its suggestions as buttons ("Trial balance at year end · 82%"), an item picker and Discard.
- **Upload for the client:** opens a small dialog with the note field.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-4, AC-5 | integration | On-behalf provenance; assign creates evidence and links it; discard |
| AC-2, AC-3 | unit and integration | Matching scores and words; contributor scoping |
| AC-1 to AC-6 | component (vitest) | Inbox panel, suggestions, assign, discard, states |

## 19. Rollout
One evidence migration. No flag.

## 20. Open questions
- [ ] **Q1: on-behalf provenance.** *Recommendation:* source `firm_upload_for_client`, the team member as uploader, and an optional note. The client sees it as "Added by your auditor".
- [ ] **Q2: matching method.** *Recommendation:* rules over the cleaned file name (word overlap with description and area, plus tier and dataset keywords), with at most three suggestions and always a person's confirmation.
- [ ] **Q3: model matcher.** *Recommendation:* deferred to its own spec with the matcher evaluation suite (a Phase 2 exit item), measured against this rule baseline.
- [ ] **Q4: what waits for staging.** *Recommendation:* email reply matching (inbound email) and screening uploaded files (malware scanning, SPEC-020 Q7) stay in increment 6 but are built after TASK-014.
- [ ] **Q5: protected paths.** *Recommendation:* an approval file covering:
  - `evidence/**`;
  - `backend/tests/unit/**`;
  - `schema_check.py` (the new table);
  - `banned_patterns.py` (if a lookup needs an exemption).

  The matrix, `api/app.py` and identity don't change.

## 21. Future / explicitly deferred
- Email reply matching; upload screening; the model matcher.
- Previews after scanning.
