# Collaboration · comments v2 and to-dos

| Field | Value |
|---|---|
| Version | v1 |
| Status | final (P-05-T16, 2026-11-12, DEC-4315): every route live behind `collaboration.v2` (P-05-T05 to T09; AUD-29 behind `audit_trail.engagement_activity`, P-05-T11); additive changes only from here |
| Provider epic | P-05 (SPEC-650; ADR-236 proposed) |
| Consumers | SHL-17, SHL-18 (P-05-T10, T13); host epics that register anchors (A-04 AUD-09 rows, A-09, A-10, K-03, X-01, F-08 row drawer) |
| Flag | `collaboration.v2` (P-05-T02): off → 404 |
| Code | `backend/src/abacus/modules/collaboration/contract.py`; fixtures `apps/web/src/fixtures/seed/collaboration.ts` |

## Who may call it
| Operation | Method and path | Action |
|---|---|---|
| Threads on one anchor | `GET /v1/comment-threads?anchor_kind=&anchor_id=&locator=&status=` | `comment.read` |
| Counts per anchor (≤ 200) | `POST /v1/comment-threads/counts` | `comment.read` |
| Open a thread | `POST /v1/comment-threads` | `comment.create` |
| Reply or Correct… | `POST /v1/comment-threads/{thread_id}/comments` | `comment.create` |
| Redact… (fresh MFA) | `POST /v1/thread-comments/{comment_id}/redact` | `comment.redact` |
| Resolve, Reopen | `POST /v1/comment-threads/{thread_id}/resolve`, `/reopen` | `comment.resolve` |
| Mute, mark read | `POST /v1/comment-threads/{thread_id}/mute`, `/read` | `comment.read` |
| Share with a grant scope | `POST /v1/comment-threads/{thread_id}/share` | `comment.share` |
| Convert to review note (C3) | `POST /v1/comment-threads/{thread_id}/convert-to-review-note` | `review_note.raise` |
| Mention candidates | `GET /v1/engagements/{engagement_id}/mention-candidates?q=` | `comment.create` |
| Assignee candidates | `GET /v1/engagements/{engagement_id}/assignee-candidates?q=` | `todo.assign` |
| Create a to-do | `POST /v1/todos` | `todo.create` |
| My to-dos; to-dos on an anchor | `GET /v1/todos?assignee=me&status=` · `GET /v1/todos?anchor_kind=&anchor_id=` | `todo.read` |
| Counts per anchor | `POST /v1/todos/counts` | `todo.read` |
| One to-do | `GET /v1/todos/{todo_id}` | `todo.read` |
| Autosave (`If-Match`) | `PATCH /v1/todos/{todo_id}` | `todo.update` |
| Reassign | `POST /v1/todos/{todo_id}/assign` | `todo.assign` |
| Complete; Reopen (= Undo) | `POST /v1/todos/{todo_id}/complete`, `/reopen` | `todo.complete` |
| Move within the engagement | `POST /v1/todos/{todo_id}/move` | `todo.update` |
| Soft delete | `DELETE /v1/todos/{todo_id}` | `todo.delete` |
| Checklist (≤ 8) | `POST /v1/todos/{todo_id}/checklist-items` · `PATCH`/`DELETE …/{item_id}` | `todo.update` |
| Seen by the assignee | `POST /v1/todos/{todo_id}/seen` | `todo.read` |

The agent, client roles, `client_service` and platform support hold none of the new actions
(P-05-T02, DEC-3103); a client principal gets 404 on every route (no P-05 anchor is client-visible).

## Shapes
`ThreadOut` (anchor facts, status, visibility, `opened_on_version_no`, comments, events,
`allowed_actions`), `ThreadCommentOut` (body Restricted, null when redacted;
`corrects_comment_id`, `corrected_by_comment_id`, `ThreadRedactionOut`), `CommentPostedOut`
(thread, notified people for the delivery line), `MentionCandidatesOut` (team entry, members,
greyed `not_on_engagement`), `TodoOut` (`overdue` and `bucket` derived in the firm's time zone,
checklist ≤ 8, `version` for `If-Match`), `TodoPageOut` (`counts`: `overdue`, `today`,
`this_week`, `later`, `no_date`, `open`, `done`).

## Status words
`comment_thread` (Open, Resolved), `todo` (Open, Done; Overdue derived) — C2.

## Errors
409 `anchor_kind_not_registered`, `anchor_not_shareable`, `already_redacted`,
`thread_already_resolved`, `stale_version`, `archived`; 404 `anchor_not_found`; 422
`anchor_scope_mismatch`, `mention_not_allowed`, `assignee_not_allowed`, `empty_comment`,
`comment_too_long` (over 4,000), `correction_not_allowed`, `checklist_full`. `facts` carry
identifiers only.

## Events and audit
Outbox: `comment.created`, `mention.created`, `comment_thread.resolved`, `comment_thread.reopened`,
`todo.created/updated/completed/reopened/moved/deleted`, `todo.assigned` — identifiers and enums
only. Audit actions as P-05 §4.7; only `todo.deleted` and `comment.redacted` show in AUD-29 (OQ-4).

## Fixture mode
`collaborationHandlers({shl17, shl18})` serves SHL-17 a–f and SHL-18 a, b, b2, c, d, e, f from
`seed/collaboration.ts`; writes answer 501 as live does until P-05-T05 and T06.
