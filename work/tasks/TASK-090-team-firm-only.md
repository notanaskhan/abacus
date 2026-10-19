---
id: TASK-090
title: An engagement's team is its firm members only — client users broke the engagement and team reads (the Requests board failed) and could be mentioned on internal comments
spec: SPEC-020
acceptance_criteria: [AC-3]
risk_zone: red
status: done
branch: task-090-team-firm-only
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Return only firm members from `engagement_members_of`. Client users share `engagement_members`, under the roles `client_admin` and `client_contributor`.

## Scope
**In**
- `identity/repository.py` `engagement_members_of` filters to `ENGAGEMENT_ROLES`. This fixes three things:
  - `GET /engagements/{id}` and `/team` returned 500 (a `ValidationError` on `TeamMemberOut.role`) whenever a client user was a member. The Requests board showed "Couldn't load the evidence board".
  - Mentions on internal comments (`requests/comments.py`) labelled client contributors as "firm", so they could be mentioned on an internal note.
  - The self-join notification (`notifications/catalogue.py`) went to client users.

**Out**
- A regression integration test: deferred under the founder's "build fast" instruction. It is owed under ADR-078.

## Plan
Approved by founder (2026-10-19, "proceed with your recommendations"). Path: `backend/src/abacus/modules/identity/repository.py`. Approval file: `work/approvals/TASK-090.yaml`, expires 2026-10-26.

## Definition of done
- [x] The Requests board loads on the dev stack for an engagement with a client user.
- [x] `make check-fast` passes.

## Gotchas and discoveries
- Found during the UX screenshot pass. Every engagement with an invited client hit the error.
