---
id: SPEC-021
title: Request item detail
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-016, ADR-039, ADR-052, ADR-104]
related_specs: [SPEC-000, SPEC-004, SPEC-016, SPEC-020]
created: 2026-10-09
updated: 2026-10-09
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
A firm-side page for one request item that brings together everything about it:
- what was asked;
- every evidence version received, with its provenance (pulled from the ledger or uploaded by the client);
- each version's screening result, with its citations marked verified or not;
- the review decision.

From the page a reviewer can download a version and accept, reject or send back the newest one. This is the "item detail with provenance, results and verified citations" part of increment 6, on top of APIs that mostly exist.

## 2. Problem and context
- **The information is scattered:** the Board shows one line per item, and the review queue shows one version at a time.
- **Earlier versions can't be seen:** nothing shows an item's earlier versions, who supplied each one, or the evidence itself.
- **Evidence can't be downloaded:** `read_version` (authorised, audited and fingerprint-verified) exists in the evidence service, but no route serves it.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement team (partner, manager, senior, staff, reviewer) | View the item and its evidence; download (`evidence.read`) |
| Reviewers with decision rights | Accept, reject or send back (existing `evidence.accept` and `evidence.reject`) |

## 4. Goals and non-goals
**Goals**
- **Page** `/engagements/$id/items/$itemId`, opened from each Board card and each review-queue entry.
- **Header:**
  - description, audit area, tier and status;
  - "Hidden from client" state, and the client assignee's name;
  - Retrieve (existing) for retrievable items.
- **Evidence versions** (newest first). Each shows:
  - version number and how it arrived:
    - "Retrieved from {source}", with period and pull time;
    - or "Uploaded by {name}", with file name;
  - when, size, the first 12 characters of its fingerprint, and media type;
  - a **Download** button.
- **Screening** for each version:
  - action, confidence and rationale, with the AI tag (SPEC-016);
  - each citation with its cell, quote and value, marked "Verified" or "Not verified" with the reason;
  - unverified claims listed separately;
  - all model text shown as plain text.
- **Decision** on the newest version:
  - its current state (awaiting review, accepted, rejected or sent back, with reason codes and who decided);
  - Accept, Reject and Send back (with reason codes), each confirmed, through the existing routes;
  - the buttons appear only where the matrix allows, and the API stays the authority.
- **Backend additions:**
  - `GET /v1/engagements/{id}/request-items/{item_id}/versions` (`evidence.read`): the versions fulfilling the item, newest first, with provenance, uploader name and file name for uploads, and each version's review decision;
  - `GET /v1/engagements/{id}/evidence-versions/{version_id}/content` (`evidence.read`): the bytes as an attachment, audited `evidence_version.read`, fingerprint-verified (Q1).

**Non-goals**
- In-browser preview or rendering of evidence (Q1).
- The item's full audit trail (Q3).
- Client-side item detail (the client portal stays as SPEC-020 built it) (Q4).
- Comments or notes on items.

## 5. User stories and acceptance criteria
- **AC-1** Given an engagement team member, when they open an item, then they see its header and every evidence version newest first, each with provenance (retrieved: source, period, pull time; uploaded: uploader and file name), size, fingerprint prefix and media type.
- **AC-2** Given a version, when they choose Download, then the file arrives as an attachment with its stored media type, the read is audited, and content whose fingerprint doesn't match is refused.
- **AC-3** Given a screened version, then its action, confidence, rationale and every citation show, each marked verified or not with the reason, with the AI tag, as plain text.
- **AC-4** Given the newest version and a user allowed to decide, then Accept, Reject and Send back (with reason codes) are offered, confirmed and applied through the existing routes, and the page updates. Users without the right see the decision state only.
- **AC-5** Given someone outside the engagement, or a client user, then the versions and content routes refuse them (403), and the page shows "not allowed".
- **AC-6** Given every state, then loading, empty ("No evidence yet"), error and not-allowed states exist, and colours come only from tokens.

## 6. Behaviour and flows
1. Board card → "Open". The detail page loads the item (from the items list), its versions, screening results and reason codes.
2. A decision invalidates the versions, items and review queue. Download uses a fetch with the bearer token, then saves through a blob link, so the token never appears in a URL.

## 7. Domain and data changes
None.

## 8. Interfaces
The two routes in §4, plus the existing routes:
- `request-items`;
- `screening-results`;
- the three `decision/*` routes;
- `review-reason-codes`;
- `retrievals`.

## 9. Authorisation and tenancy
- **Versions and content:** `evidence.read` on the engagement. Client roles aren't granted here: `read_version` checks at engagement level without item facts, so clients are refused (Q4).
- **Decisions:** unchanged.

## 10. AI behaviour
None new. Screening output is shown with the AI tag and verification marks, and is never presented as a decision (ADR-005).

## 11. Integrations
None.

## 12. Edge cases and failure modes
- **An item with no evidence:** the empty state, plus Retrieve or a note that the client can upload.
- **A version linked to two items:** shown on both.
- **The stored object is missing or tampered with:** download fails with "This file couldn't be verified", and the incident is logged (existing `IntegrityError`).
- **Large files:** streamed. Uploads are at most 25 MB; trial balances are small.

## 13. Security and privacy
- **Attachment only:** downloads are served as `Content-Disposition: attachment` with `X-Content-Type-Options: nosniff`, never inline (ADR-052).
- **File names:** sent as the cleaned upload name, ASCII-safe.
- **Untrusted text:** file names, rationale, quotes and values are plain text.

## 14. Audit trail and evidence integrity
- **Reads:** every download records `evidence_version.read` (ADR-104).
- **Integrity:** content is checked against its fingerprint before it's served (ADR-016).

## 15. Observability
Download counts and integrity failures.

## 16. Performance and scale
An item has few versions; one request each.

## 17. UX
The SPEC-016 shell, in a two-column layout:
- the versions timeline on the left;
- the selected version's screening and decision on the right.

On narrow screens they stack.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1, AC-2, AC-5 | unit and integration | Versions route content and refusals; download audited, attachment headers, fingerprint mismatch refused |
| AC-1 to AC-6 | component (vitest) | Page with mocked client: timeline, citations, decisions by right, states |

## 19. Rollout
No migration and no flag.

## 20. Open questions
- [ ] **Q1: viewing evidence.** *Recommendation:* download as an attachment only, with no in-browser preview. Rendering client files in the app is the riskiest path for hostile content (ADR-052) and waits for malware scanning (TASK-014).
- [ ] **Q2: where the versions list lives.** *Recommendation:* a new evidence route that joins fulfilments (through the requests API) to versions and decisions, rather than the SPA stitching the engagement-wide lists together.
- [ ] **Q3: item history.** *Recommendation:* deferred. The audit trail per item belongs with export (increment 7).
- [ ] **Q4: clients.** *Recommendation:* firm-side only. Clients keep the SPEC-020 upload history and can't download evidence for now.
- [ ] **Q5: protected path.** `evidence` is protected, so the task needs your approval file. *Recommendation:* yes, covering `evidence/**`, `backend/tests/unit/**`, and `banned_patterns.py` if the versions lookup needs a LIST-001 exemption.

## 21. Future / explicitly deferred
- In-browser preview after malware scanning.
- Item audit history (increment 7).
- Comments on items.
