---
id: TASK-037
title: Request item detail
spec: SPEC-021
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: amber
status: done
branch: task-037-request-item-detail
worktree:
created: 2026-10-09
updated: 2026-10-09
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-021 (approved, Q1–Q5): the firm-side request item detail page, with the item's versions route and the audited download route.

## Scope
All of SPEC-021.

## Context to load
- Spec: `docs/specs/SPEC-021-request-item-detail.md`
- Code: `evidence` (`read_version`, `uploads.py`, repository `decision_for`, models), `requests.api` (`read_item`, `read_item_versions`), `apps/web` `Board`, `Review` (decision actions), `screening-results`

## Plan
- [x] Plan approved by human (founder, 2026-10-09: D1–D4). Approved by founder: paths listed under *Protected paths*

### Design (for founder review)
1. **Versions route** (`evidence/item_detail.py`): `item_versions(ctx, engagement, item)`.
   - **Authorisation:** `evidence.read` on the engagement with the item's facts. Client roles still need item-level grants that this route doesn't give (SPEC-021 Q4), so the service refuses any actor whose role on the engagement is a client role.
   - **What it reads:**
     - the item's version IDs through `requests.api.read_item_versions`;
     - one query for those versions with their evidence items, plus the decisions for those versions on this item (D1);
     - uploader names through `identity.api.names_of`.
   - **Each entry:**
     - version, number, method, source, period, `pulled_at`, `created_at`, size, media type, the full fingerprint (the UI shows 12 characters);
     - for uploads, the file name (the evidence item's title) and the uploader;
     - the decision on this item (kind, reason code, who, when), or none.
2. **Download route** `GET …/evidence-versions/{version_id}/content` (`evidence.read`):
   - `read_version` (authorised, audited and fingerprint-verified) returned as a `Response`;
   - headers: `Content-Disposition: attachment` with an ASCII-safe file name (the upload's name, or "trial-balance-{period}.xlsx" for retrieved ones), the stored media type, `X-Content-Type-Options: nosniff` and `Cache-Control: no-store`;
   - a failed verification becomes a 409 `integrity_failed`, logged;
   - the client role is refused as in item 1.

   `AbacusRouter` requires a response model, so this route declares `bytes`, and the OpenAPI document shows a binary body (D2).
3. **Web:**
   - `ItemDetail.tsx` at `/engagements/$id/items/$itemId`:
     - the header from the items list;
     - the versions timeline;
     - the selected version's screening, from `screening-results` filtered by version, with citations as plain text and verification badges;
     - the decision panel.
   - **Decision actions:** the Accept, Reject and Send-back controls in `Review.tsx` move to a shared `DecisionActions` component, so the Review screen and this page use the same code (D3). They're shown when the user's engagement role may decide; the API stays the authority.
   - **Download:** an authenticated fetch, then a blob link (the token never appears in a URL).
   - **Links:** "Open" on each Board card and review-queue entry.

**Protected paths (approval file):** `backend/src/abacus/modules/evidence/**`, `backend/tests/unit/**`, `backend/src/abacus_tools/quality/banned_patterns.py` (a LIST-001 exemption for the item-scoped versions lookup). I checked the rest:
- `api/app.py`: no new routers (the evidence router gains routes);
- the matrix: no change;
- `schema_check.py`: no grants or tables change;
- identity: only `names_of` and `engagement_role_of`, which already exist.

### Questions for approval
- **D1. Read decisions for exactly the versions on this item in one query (an exempt, item-scoped lookup), rather than per version?** *Recommendation: yes.*
- **D2. The download route declares `bytes` as its response model and returns the file as an attachment?** *Recommendation: yes.* This keeps the router's rule that every route declares a response model.
- **D3. Move the decision controls out of `Review.tsx` into a shared component used by both screens?** *Recommendation: yes.*
- **D4. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [x] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] Every query is tenant-scoped; every endpoint checks authorisation
- [x] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-09` — Implemented:
  - the item versions route (provenance, uploader and file name, the decision on this item) and the audited, verified attachment download;
  - the item page (header, versions timeline, screening with verified citations through `AgentText`, decision panel by role, blob download);
  - the shared `DecisionActions`, now used by the review queue too;
  - "Open" links from Board cards and queue entries.

  Fixes along the way:
  - the `evidence.uploaded` notification link pointed at `/board`; the route is `/requests`;
  - the Board tests now render inside a router (the card links need one).

  Tests and checks:
  - backend unit 8,968 and web 153 passed; the gates pass;
  - a local smoke on seeded evidence passed (versions listed, a 6 KB trial balance downloaded and verified).
- `2026-10-09` — SPEC-021 approved and merged (#68). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
