---
id: TASK-106
title: "SPEC-042: client words for requests, \"This doesn't apply\" with a reason (and undo), \"Mark as done\"; the firm sees both"
spec: SPEC-042
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: done
branch: spec-042-portal
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
Migration 0063; requests module `client_responses.py` with routes on the request-items router; matrix actions; the portal UI (`ClientEngagement.tsx`) and the firm's Board. Approved by founder (2026-10-20, "proceed").

## Done
- Migration 0063 (`client_item_responses`, `client_list_done`, insert-only); `requests/client_responses.py`.
- Routes on request-items: `GET /client-responses`, `POST /{id}/client-response`, `POST /{id}/client-response/withdraw`, `GET` and `POST /client-done`.
- Matrix: `client_item.respond` (client admin on client-visible items, the assigned contributor) and `client_list.mark_done` (client admin).
- Portal: the client vocabulary (`STATUS.clientRequest`); the "This doesn't apply…" reasons and note; "You said: …" with Undo; a done bar ("n of m done", "Mark as done" enabled when everything's done, "Marked done by …").
- Firm: a "Client: doesn't apply · reason" badge on request rows; "Marked done by …" in the Requests header.

## Definition of done
- [x] `test_client_responses.py` (3), `spec042portal.test.tsx` (4); the portal and board screen tests pass; `make check-fast` passes.
- [ ] Not walked live; owed: ADR-078 integration tests (visibility of responses to contributors, `list_not_done`).
