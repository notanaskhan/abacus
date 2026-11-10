# SHL-18 · Comments and @mentions

| Field | Value |
|---|---|
| Route and params | Local state anchored to the object's chip; `?focus=<anchorKey>&thread=<threadId>` hydrates it once ("Copy link"); dock tab `?dock=comments` and row-drawer tab `?ov=row:<rowKey>` are mounted by their host epics |
| Template and host frame | O1 Popover 420 or a dock tab (360) or a drawer tab (480) · `Wave 0 - Shell.dc.html#shl18` |
| Surface | firm (shared threads reach the portal only through a grant scope, A-09) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-18 Comments and mentions/` (README.md, spec.md) |
| Epic and tasks | P-05 · bundle T02 · stubs T03 · migration T04 · service T05 · kinds and anchors T09 · screen T10 · journeys T15 · SPEC-650 · ADR-236 |
| Manifest status | planned (fixture with P-05-T03; live with P-05-T10 behind `collaboration.v2`, after ADR-236 is accepted) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a Default popover | margaret-okonkwo | Mon Sep 14, 2026 12:35 PM | Thread on Exceptions!A3 with "@Hannah Leclerc this cutoff item drives AJE-1 — show it as factual on the SUM." and the delivery line "Hannah Leclerc notified in Accrued and by email · 12:35 PM" | live (T10) |
| b Mention picker | margaret-okonkwo | 12:34 PM | Composer "@Ha": Hannah Leclerc · Audit Senior Manager, "Ha" in 500 weight | live (T10) |
| b2 Whole team | margaret-okonkwo | 12:35 PM | Composer "@": "Northwind PY2025 team · 5 people" and five members, Margaret "(you)" | live (T10) |
| c Restricted person | margaret-okonkwo | 12:35 PM | "@Si": Simone Baptiste greyed under "Not on this engagement"; a test-only wall on Northwind's client proves a walled person's absence | live (T10, + test wall) |
| d Resolved · dock tab | hannah-leclerc | Wed Oct 21, 2026 2:10 PM | FSP-01 Granite Peak "Dividends paid": MO 10:40 AM, HL 11:05 AM with citation [1], resolved | fixture (A-10) |
| e Empty · row drawer | simone-baptiste | Thu Sep 24, 2026 | SURL-03 row drawer, no threads: "No comments yet." / "Comments are internal and never block sign-off." | gallery (host T18, F-08/K-03) |
| f Shared with a component auditor | omar-haddad | Wed Sep 23, 2026 | Harlow & Pike, Pruett & Lang shared thread (Renee Pruett, Omar Haddad); "Replies here are visible to ‹org›" | fixture (A-09) |
| loading, error, not allowed, off | as above | — | as SHL-17 | live |

Parity tier: Tier C on a, b, b2, c, locked at S37; d, e, f report-only until their host epics; Tier D
blocking on popover 420 and picker 300.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/comment-threads?anchor_kind=&anchor_id=&locator=&status=` | threads with comments; redacted bodies as the stub | `comment.read` | internal threads never to client principals (INV-4) |
| read | `POST /v1/comment-threads/counts` | ≤ 200 anchors | `comment.read` | — |
| read | `GET /v1/engagements/{engagement_id}/mention-candidates?q=` | members, team entry, greyed non-members; walled people absent | `comment.create` | no hidden counts (DEC-43) |
| write | `POST /v1/comment-threads` · `POST …/{thread_id}/comments` | `ThreadOpenIn` · `CommentPostIn` (`corrects_comment_id` for Correct…) | `comment.create` | 409 `anchor_kind_not_registered`; 422 `mention_not_allowed`, `empty_comment`, `comment_too_long`, `correction_not_allowed` |
| write | `POST /v1/thread-comments/{comment_id}/redact` (fresh MFA) | `RedactIn` (reason 1–500) | `comment.redact` | firm admin; 409 `already_redacted` |
| write | `POST …/resolve` · `…/reopen` | — | `comment.resolve` | 409 `thread_already_resolved` |
| write | `POST …/mute` · `…/read` | `{muted}` · — | `comment.read` | — |
| write | `POST …/share` | grant scope | `comment.share` | 409 `anchor_not_shareable` |
| write | `POST …/convert-to-review-note` | — | `review_note.raise` | hidden on shared threads |

Every endpoint is in `docs/contracts/collaboration.md` (P-05-T03); 501 until P-05-T05.

## Status
`comment_thread` (`open`, `resolved`).

## Copy
"Comments never block sign-off. Review notes do.", "Mentioned people are notified in Accrued and by
email", "Comment, or type @ to mention…", "Only people on this engagement can be mentioned. Add
people in Team & roles (ENG-05).", "No comments yet.", "Comments are internal and never block
sign-off.", "Converted to review note · now blocks sign-off until cleared", "Replies here are visible
to ‹org›", "Correct…", "Redact…", "Corrected below", "Redacted by ‹person› on ‹date›: ‹reason›".

## Deviations
- DF-18 (ADR-236): the canvas's ··· menu offers Edit and Delete…; the product offers Correct…
  (author) and Redact… (firm admin, reason, fresh MFA) and never Edit or Delete.
- OQ-8: the composer's paperclip is not built (SPEC-032 forbids attachments); design follow-up.
- SHL-18a and b2 have no letter in the spec's STATES list (added during the build).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Convert to to-do…" | SHL-17 | handoff link (P-05) |
| "Convert to review note…" | AUD-17 | handoff link (P-04 review notes) |
| Anchor chip | AUD-09 | handoff link (A-04) |
| Shared org | POR-23 | planned (A-09) |
| Row drawer host (SURL-03, not a manifest screen yet) | — | planned (K-03) |
| Citation [1] | SHL-08 | handoff link (C4) |

## Acceptance
- Every artboard letter above carries live, fixture-only or gallery with its owning task or epic.
- No Edit or Delete affordance; Accrued Agent is never a mention candidate; no agent-owned control
  carries Approve, Sign off, Release, Send, Post or Decide.
