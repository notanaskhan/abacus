# SHL-17 · To-do drawer

| Field | Value |
|---|---|
| Route and params | `?ov=todos:mine` · `?ov=todos:<todoId>` · `?ov=todos:new[:<nonce>]` (the nonce holds the prefill in `overlayPayloadStore`) · typed service `openToDo(id)` |
| Template and host frame | O2 Drawer 480, peek variant (no scrim, no focus trap; focus moves in and returns) · `Wave 0 - Shell.dc.html#shl17` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-17 To-do drawer/` (README.md, spec.md) |
| Epic and tasks | P-05 · bundle T02 · stubs T03 · migration T04 · service T06 · seed T12 · screen T13 · journeys T15 · SPEC-650 |
| Manifest status | planned (fixture with P-05-T03; live with P-05-T13 behind `collaboration.v2`) |

## States
Clock is the demo clock (DEC-27), CT. Persona slugs follow F-04.

| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a Default | margaret-okonkwo | Mon Sep 14, 2026 12:36 PM (E0) | To-do on Northwind Exceptions row 6 for Marcus Delaney, due Sep 16, checklist 0 of 4, one comment, Notify "In Accrued and by email" | live (T13) |
| b New | margaret-okonkwo | 12:35 PM | New to-do from row 6 ··· Add to-do…; assignee picker open with MO, HL, MD, AC, TW; "Create to-do" disabled until a title and an assignee are set | live (T13) |
| c Assigned to me | marcus-delaney | 12:40 PM | Same to-do; banner "Assigned to you by Margaret Okonkwo · 12:36 PM" | live (T13) |
| d Overdue | kira-ross | Mon Sep 21, 2026 8:30 AM (E2) | Tessellate E-2 · CC8.1 · TES-52, due Sep 18, created by Laura Kemp Sep 15, checklist 1 of 2; chip "Overdue · Sep 18" | fixture (ATT-06, X-01) |
| e Done | cole-hart | Mon Sep 28, 2026 | "Re-request 2 SURL files", BH-FS-430 SURL request, done Sep 28, "40 of 40" | fixture (SHT-01, K-03) |
| f My to-dos | marcus-delaney | 12:40 PM | "Open 4 · Done": OVERDUE 1 (Sep 11, from HL), TODAY 1 (created by you), THIS WEEK 2 (Sep 16 from MO, unread; Sep 18 from HL); footer "4 open · Northwind PY2025" | live (T13; golden 4 = 1 + 1 + 2) |
| loading, error, not allowed, off | as above | — | never-resolving handler; error; Lena Park on Ashford (not allowed); `collaboration.v2` off: the designed flag-off state, routes answer the P-36 flag-off error | live |

The handoff README lists SHL-17c's viewer as Margaret Okonkwo; the artboard is "Assigned to me" and
the epic's fixture table names Marcus Delaney, so the contract uses marcus-delaney.

Parity tier: Tier C (threshold 0.20, ≤ 3%) on a–f, locked at S37; Tier D blocking on drawer 480 and
header 46.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/todos?assignee=me&status=` | list envelope, `counts` {overdue, today, this_week, later, no_date} | `todo.read` | firm-scope rows: creator or assignee only |
| read | `GET /v1/todos?anchor_kind=&anchor_id=` · `POST /v1/todos/counts` | list · counts per anchor | `todo.read` | — |
| read | `GET /v1/todos/{todo_id}` | `TodoOut` with checklist and `allowed_actions` | `todo.read` | — |
| read | `GET /v1/engagements/{engagement_id}/assignee-candidates?q=` | members only, never the agent | `todo.assign` | — |
| write | `POST /v1/todos` | `TodoCreateIn` | `todo.create` | agent 403 (INV-1) |
| write | `PATCH /v1/todos/{todo_id}` (`If-Match`) | `TodoPatchIn` | `todo.update` | 409 `stale_version` |
| write | `POST …/assign` · `…/complete` · `…/reopen` · `…/move` · `…/seen` | — | `todo.assign` · `todo.complete` · `todo.complete` · `todo.update` · `todo.read` | Undo calls only `…/reopen` |
| write | `DELETE /v1/todos/{todo_id}` | soft delete | `todo.delete` | creator, assignee or manager+ |
| write | `POST|PATCH|DELETE …/checklist-items[/{item_id}]` | ≤ 8 items | `todo.update` | 422 `checklist_full` |

Every endpoint is in `docs/contracts/collaboration.md` (P-05-T03); 501 until P-05-T06.

## Status
`todo` (`open`, `done`; Overdue derived at read time in the firm time zone, never stored).

## Copy
"To-dos are internal. No client sees them, and they never block sign-off.", "To-dos go to people. To
have the agent do work, run it from the dock.", "What needs doing?", "Create to-do", "Mark done",
"Reassign…", "Reopen", "Up to 8 items", "To-do done · Undo", "Assigned to you by ‹name› · ‹time›",
"Saved · ‹time›". Copy keys live in `apps/web/src/screens/SHL-17/copy.ts` with the screen task; L2:
"To-do" hyphenated, never "task".

## Deviations
- SHL-17a has no letter in the spec's STATES list (added during the build).
- The canvas draws C-27, C-29 and C-30 inline; the product mounts them from `domain/collaboration`.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Draft request…" | SHL-14 | handoff link (prefilled; a person sends it) |
| Linked object chip | AUD-09 | handoff link (A-04) |
| Linked object chip | ATT-06 | planned (X-01) |
| Linked object chip | SHT-01 | planned (K-03) |

## Acceptance
- Every artboard letter above carries live or fixture-only with its owning task or epic.
- The agent is never an assignee or an actor; no agent-owned control carries Approve, Sign off,
  Release, Send, Post or Decide.
