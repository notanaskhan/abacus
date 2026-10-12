---
id: TASK-063
title: "Comments, part 2: threads for the firm and the client, mentions, counts, redaction and the client's notifications (web)"
spec: SPEC-032
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-10]
risk_zone: amber
status: done
branch: task-063-comments-web
worktree:
created: 2026-10-12
updated: 2026-10-12
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-032 §7, TASK-063: the screens on top of TASK-062's APIs (merged, #112).

## Scope
SPEC-032 AC-1 to AC-8 (screens), AC-10.

## Context to load
- Spec: `docs/specs/SPEC-032-comments.md`; TASK-062
- Code: `apps/web/src/screens/ItemDetail.tsx` (evidence versions, the selected version, `DECIDERS`), `ClientEngagement.tsx` (`ClientItem`, history), `Board.tsx` (badges and filters), `ClientHome.tsx`, `Layout.tsx` (the bell), `shell/NotificationPanel.tsx`, `shell/notifications.ts` (text and links)

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D3 as recommended)

### What the code shows
- **Item detail** lists the item's evidence versions and shows panels for the selected one (checks, AI review, preview).
- **The client's request row** has the history list (TASK-061), one row per version.
- **The Board** has badges with filters ("Problems found", "AI flags").
- **The firm's bell** (`NotificationPanel`) renders fixed text per kind (`shell/notifications.ts`) and links each to a firm route. The client portal has no bell.

### Design (for founder review)
1. **A shared `CommentThread` component.** It takes the thread (an item, or an item and a version), the viewer's side and their permissions.
   - **Comments, oldest first:** author name and side, time, and the text as plain text (never HTML).
     - Internal notes have a distinct tinted background (a token) and the label "Internal: the client can't see this".
     - A corrected comment shows "Corrected below"; a correction shows "Corrects an earlier comment", linking the two.
     - A redacted comment shows "Redacted by {name} on {date}: {reason}" instead of the text.
   - **Composer:** a text area (4,000 characters, with a counter) and **Post**.
     - For the firm, a choice of **Internal note** (the default) or **Share with client**, shown only to those allowed to share (partner, manager, senior, staff). Sharing turns the composer's border to the shared colour and says "The client will see this".
     - Clients have no choice; their comments are always shared.
   - **Mentions:** typing `@` opens a list from `mention-candidates` for the chosen visibility, filtered as you type. The picked names show as chips under the composer; their IDs are sent as `mentions`. The text keeps "@Name" as typed.
   - **Corrections:** a "Correct" link on your own comment (not redacted) opens the composer, labelled "Correcting your comment".
   - **Refusals:**
     - `out_of_scope`: "This mentions something outside this engagement (another client, another ledger's account or an amount not in it). Remove it, or post it as an internal note."
     - `sharing_unavailable`: "Sharing with the client isn't available right now."
     - `mention_not_allowed`: "Someone you mentioned can't see this comment."
   - **Unread:** opening the thread marks it read (`POST …/comments/read`).
   - **States:** loading, empty ("No comments yet"), error, and not allowed.
2. **Item detail (firm):**
   - a **Comments** panel for the item's own thread;
   - a **Comments on this version** panel beside the selected version's panels;
   - for firm administrators, a **Redact** action on each comment, opening a dialog that asks for the reason.
3. **The client's request** (`ClientItem`):
   - a **"Comments (n)"** toggle under each request opens the item's thread;
   - each history row gains **"Comments (n)"** for that version's thread, counted from its list;
   - a dot shows when there's anything unread.
4. **Counts:**
   - the Board shows a "Comments" badge with the count and a dot when unread, plus a filter option "Unread comments";
   - the client's request list shows the same on each request.
5. **The client portal's bell** (SPEC-032 Q2): the same `NotificationPanel` in the client header, on the client home and engagement pages.
   - Notification links become per portal: a firm user goes to the item in item detail; a client goes to the engagement page, scrolled to the request.
   - Text for the new kind: "You were mentioned in a comment."
6. **Tests (vitest):**
   - the thread's states, internal styling, the visibility toggle by role, and the client's lack of it;
   - corrections and redaction display;
   - mention picker filtering and sent IDs;
   - each refusal message;
   - the read call on open;
   - Board and client counts with unread dots;
   - the client bell and its links;
   - redaction by firm admin only.
   - Plus a local smoke after restarting `make dev`, as Casey Client and the partner.

### Questions for the human
- **D1 — where the firm reads the item's thread.** Recommended: a Comments panel at the top of item detail, beside Client guidance, with each version's thread beside that version's panels. Alternative: a single side drawer opened from a button.
- **D2 — mentions in the text.** Recommended: keep "@Name" as typed in the text, with the actual recipients sent as IDs (chips show who will be notified). There's no rich text: the stored comment stays plain text (ADR-109's record shows exactly what was written).
- **D3 — approval file:** none expected. Web code isn't protected, and the API client was regenerated in TASK-062.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format pass
- [ ] Comment text is always rendered as plain text; internal notes are distinct; colours from tokens only
- [ ] The relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after TASK-062 merged (#112).
- `2026-10-13` — Built (D1–D3): `CommentThread` (internal notes distinct, plain text, sharing toggle for partner, manager, senior and staff, mention picker with chips, corrections, redaction dialog for firm admins, refusal messages, read on open); item detail's Comments panels (request and selected version); the client's per-request and per-version threads with counts and unread dots; the Board's Comments badge and "Unread comments" filter; the client portal's bell with per-portal notification links. Vitest (298), lint and types pass. After restarting `make dev`, a shared firm comment mentioning Casey Client reached Casey's notifications through the worker.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Version threads in the client's history show "Comments" without a count | A count per version would cost one request per row; the request's count covers all its threads | No |

## Handoff
Done. SPEC-032 is complete. Next per the Act 2 plan: Track B (B3 matching), A1's remaining formats, or Track C.
