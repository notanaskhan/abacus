---
id: SPEC-650
title: P-05 collaboration — comments v2 (SHL-18), to-dos (SHL-17) and the engagement activity log (AUD-29)
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-007, ADR-031, ADR-052, ADR-109, ADR-137, ADR-138, ADR-139, ADR-140, ADR-145, ADR-151, ADR-159, ADR-160, ADR-161, ADR-232, ADR-236]
related_specs: [SPEC-032]
created: 2026-11-09
updated: 2026-11-09
---

> **Instructions for coding agents**
> - P-05's own SPEC (P-05-T01). The design is `docs/plan/epics/P-05.md` §3 to §8; task rows are
>   `docs/plan/epics/P-05.tasks.csv`. SPEC-032 stays the spec of the live request-item comments.
> - Contracts provided: `docs/contracts/collaboration.md` (P-05-T03) and the two audit_trail
>   engagement routes (P-05-T02 stubs, P-05-T11).
> - The whole epic merges dark inside the Jan 1 – Apr 20, 2028 busy-season window (ADR-151, P-29):
>   default-off flags, expand-only migrations, no live-path edit.

## 1. Summary
Internal collaboration on any work object: comment threads anchored polymorphically (ADR-236),
to-dos assigned to people, and an engagement-scoped activity log with Human / via Agent / Policy
segments. Comments and to-dos never block a sign-off and never enter the human-gate projection;
only review notes do (R7, C3, C13). No model reads or writes any of it.

## 2. Gate check (main 7c00ad484, 2026-11-09; DEC-3102)
| Decision / ADR | On main | State | What S33 does |
|---|---|---|---|
| P-42 Generalised comments (plan alias ADR-209) | ADR-236 | **proposed** (acceptance: Ayush) | S33 builds only reversible dark work: this SPEC, the bundle (T02), 501 stubs (T03), the expand-only migration (T04). The comments v2 service (T05, S34) waits for acceptance (§11.1 R-2) |
| DEC-29, DF-18 | decision log | decided | Append-only, Correct… and Redact…, version-aware anchors (ADR-236 decisions 3–7) |
| DEC-60, DEC-61, DEC-14, DEC-43, DEC-67 | decision log | decided | As P-05 §0.1 |
| P-36 API conventions | ADR-139 | accepted | List envelope, `allowed_actions`, `Idempotency-Key`, fixed codes, 501 stubs |
| P-39 per-module registries; P-05 module map | ADR-140; ADR-137 | accepted | `collaboration/registry.py`, per-module matrix files |
| P-34 status registry | ADR-138 | accepted | `todo: open · done`, `comment_thread: open · resolved` |
| P-06 generalised `visible()` | ADR-145 | accepted | Engagement scope for threads and to-dos; firm scope by creator or assignee |
| P-07 review grammar | ADR-160 | accepted | Only review notes block L2+; `raise_review_note` inside the caller's unit of work |
| P-35 Undo | ADR-161 | accepted | Undo = `POST /v1/todos/{id}/reopen` |
| P-15 SSE | ADR-232 | proposed | Polling first; live counts are an upgrade, never a dependency |
| P-43 archive seal | ADR-159 | proposed | `archived_guard` on every new table (already the `tenant_table()` default) |
| P-29 busy-season change policy | ADR-151 | proposed | Read as below |

**The P-29 dark-merge reading (§11.1 R-1), recorded instead of minuted at a Contract Monday (solo
edition):** additive, flag-gated code that no live request executes counts as dark — a new module
file, a new route behind a default-off flag, an additive registry or anchor registration, a mount
behind a flag. Changing an existing function, route, query or table on a live path does not. The
SPEC-032 request-item path (`requests` comments, `apps/web/src/screens/CommentThread.tsx`) is
untouched (AC-39).

**Open questions decided with the plan's recommended answers (DEC-3102):** OQ-1 (AUD-29 readers:
specialist, reviewer and EQR yes; `client_service` and firm admins no), OQ-2 (CSV export is
`export.create` with fresh MFA, no dual approval), OQ-3 (system events with an agent run → via Agent;
other system and gate facts → Human; Policy only for actor kind `policy`), OQ-4 (only `todo.deleted`
and `comment.redacted` appear in Activity), OQ-5 (firm-scope to-dos: creator and assignee only),
OQ-6 (ADR-236 decision 3), OQ-7 (canary Mar 28, real firms from Apr 25), OQ-8 (no paperclip in the
composer; a design follow-up), OQ-9 (mute suppresses unread dots only).

## 3. Acceptance criteria
Transcribed verbatim from `docs/plan/epics/P-05.md` §3. Invariants: **INV-1** the agent never
decides · **INV-2** citations verified · **INV-3** walls hold · **INV-4** portal scopes isolated ·
**INV-5** audit attribution correct.

### 3.1 Comment on a work object (SHL-18a, SHL-18e)

*As Margaret, I want to tell Hannah on Exceptions row 3 how the cutoff item must appear on the SUM, without creating a gate.*

- **AC-1** *Given* `collaboration.v2` on for Brightwater Hale and Margaret on Northwind AUD-09 Exceptions, *when* Margaret opens row 3's comment chip and posts "@Hannah Leclerc this cutoff item drives AJE-1 — show it as factual on the SUM.", *then* one `comment_threads` row is created with `anchor_kind='workpaper'`, `anchor_locator={"sheet":"Exceptions","cell":"A3"}` and the workpaper version current at that moment, the body is sealed with `kernel.crypto` and never logged, the row chip reads "1", and `comment_thread.opened` + `comment.posted` audit events read "Margaret Okonkwo" (SHL-18a; INV-5).
- **AC-2** *Given* an anchor kind with no registered provider (`request_item` and `evidence_version` during the window, `sheet_row` before K-03), *when* a thread is requested on it, *then* the API answers 409 `anchor_kind_not_registered` and writes nothing (fail closed, chapter 03 §2.4).
- **AC-3** *Given* an anchor with no threads, *then* the drawer-tab variant shows "No comments yet." / "Comments are internal and never block sign-off." with the composer pinned to the bottom (SHL-18e).
- **AC-4** *Given* an empty comment or one over 4,000 characters, *then* 422 `empty_comment` or `comment_too_long` (SPEC-032 limits kept).

### 3.2 @mentions, notifications and email (SHL-18b, b2, c; SHL-04; HOME-01h)

- **AC-5** *Given* the composer reads "@Ha", *then* MentionPicker lists Hannah Leclerc · Audit Senior Manager with "Ha" in 500 weight, ↑↓ moves, Enter mentions, Esc closes (SHL-18b); *given* "@" alone, *then* it lists "Northwind PY2025 team · 5 people" and the five members, Margaret marked "(you)" (SHL-18b2). Accrued Agent is never a candidate.
- **AC-6** *Given* "@Si", *then* Simone Baptiste (a Brightwater Hale member not on Northwind) appears greyed under "Not on this engagement", is not selectable, and the footer reads "Only people on this engagement can be mentioned. Add people in Team & roles (ENG-05)."; a person walled from Northwind's client does not appear at all, and no count reveals one (DEC-43). *Given* a crafted request that mentions a non-member or a walled user, *then* 422 `mention_not_allowed` and nothing is posted (INV-3).
- **AC-7** *Given* a posted comment mentioning Hannah, *then* exactly one `mention.created` event per mentioned user produces one in-app notification of kind `mention` (SHL-04 Mentions tab, HOME-01h) and, while Hannah's preference keeps Mention email on, one email rendered from the firm's DB template; neither carries the comment body, only the anchor label and a link (DEC-61). The delivery line reads "Hannah Leclerc notified in Accrued and by email · 12:35 PM". A team mention expands to the current members at post time, the author excluded.
- **AC-8** *Given* a mentioned user who loses membership or gains a wall before fan-out, *then* no notification is created; notification reads re-check access (chapter 03 §6.4).

### 3.3 Resolve, reopen, correct, redact, mute (SHL-18d; DF-18; ADR-109 as amended by ADR-209)

- **AC-9** *Given* an open thread, *when* Hannah clicks Resolve, *then* the thread's status becomes `resolved` and a `comment_thread_events` row of kind `resolved` names Hannah (actor kind `human` by DB CHECK); the UI collapses it to "Resolved by Hannah Leclerc · ‹time› · ‹n› comments" with Reopen, and the Open/Resolved segmented counts move (SHL-18d). Sign-off preconditions are unaffected (AC-15).
- **AC-10** *When* a thread is reopened, *then* a `reopened` event is written in the same unit of work as the status projection; no other row is updated or deleted.
- **AC-11** *Given* Margaret's own comment, *then* its ··· menu offers "Correct…", which posts a follow-up with `corrects_comment_id` (the original shows "Corrected below"); it never offers "Edit" or "Delete…" (DF-18). *Given* Grace Holloway with `comment.redact` and a fresh MFA, *when* Grace redacts with a reason of 1–500 characters, *then* every reader sees "Redacted by Grace Holloway on ‹date›: ‹reason›" in its place, the sealed body is kept but never returned, and others get 403.
- **AC-12** *Given* a muted thread, *then* it adds no unread dot for that person; mentions still notify.
- **AC-13** *Given* the app role, *then* UPDATE and DELETE on `thread_comments`, `thread_comment_mentions`, `thread_comment_redactions` and `comment_thread_events` are refused by grants and triggers (append-only).

### 3.4 Conversions: to-do and review note

- **AC-14** *Given* "Convert to to-do…", *then* SHL-17b opens prefilled with the thread's anchor as the linked object; creating the to-do writes a `converted` thread event that references it, in the same unit of work.
- **AC-15** *Given* `allowed_actions` contains `review_note.raise` and the thread is internal, *then* "Convert to review note…" is offered (hidden on shared threads, SHL-18f); confirming raises an open AUD-17 review note through C3 in the same unit of work and the comment shows "Converted to review note · now blocks sign-off until cleared". *Given* an open thread and an open to-do on Northwind Internal Control and **no** open review note, *when* Hannah signs L2 in SHL-12, *then* the sign-off is allowed: comments and to-dos never block (R7, C3).

### 3.5 Shared threads (SHL-18f guard)

- **AC-16** *Given* a thread on an anchor whose provider reports `client_visible = false` (every anchor registered in P-05), *when* anyone shares it, *then* 409 `anchor_not_shareable`. *Given* a client-visible anchor and a grant covering it (C5), *then* sharing records a `shared` event and firm text in the shared thread passes `communications.api.check_scope` (SPEC-032 Q4). A client principal never receives an internal thread from any route (INV-4). State f is a fixture until A-09 registers the `component_thread` anchor.

### 3.6 Create and assign to-dos (SHL-17a, b, c)

*As Margaret, I want to hand Marcus one concrete piece of work on row 6, due Wednesday, with a short checklist, so that it is tracked without becoming a review note or a client request.*

- **AC-17** *Given* Margaret on AUD-09 row 6, *when* Margaret chooses "··· Add to-do…", *then* SHL-17b opens with the C-27 chip "Northwind · Exceptions row 6" prefilled, "Create to-do" disabled until a title and an assignee are set, and a picker of only the people on Northwind PY2025 (MO, HL, MD, AC, TW) whose footer reads "To-dos go to people. To have the agent do work, run it from the dock."
- **AC-18** *When* Margaret creates it, *then* the to-do is `open`, due Wed Sep 16, 2026, with the row text sealed as a snapshot; `todo.created` and `todo.assigned` events are written; Marcus gets one `todo_assigned` notification and one email; row 6 shows "1 To-do"; the footer reads "Saved · 12:36 PM" (SHL-17a).
- **AC-19** *Given* an assignee who is not a human member of the engagement, is walled, or is the agent principal, *then* 422 `assignee_not_allowed`. *Given* an agent context, *then* create, assign, complete, reopen, move and delete answer 403 (matrix `agent: deny`; INV-1).
- **AC-20** *Given* two editors, *when* an autosave PATCH carries a stale `If-Match` version, *then* 409 `stale_version` and the UI reloads the newer value; there is no Save button.
- **AC-21** *Given* Marcus opens a to-do assigned to Marcus, *then* the banner reads "Assigned to you by Margaret Okonkwo · 12:36 PM", the footer offers Mark done and "Reassign…", and the unread dot on that My to-dos row clears (SHL-17c).
- **AC-22** *Given* a checklist, *then* it holds at most 8 items (a ninth answers 422 `checklist_full`); each toggle is audited; "Draft request…" opens SHL-14 prefilled and a person sends it.

### 3.7 Done, overdue, undo, move and delete (SHL-17d, e)

- **AC-23** *Given* an open to-do whose `due_on` is before today in the firm's time zone (`kernel.clock`), *then* it shows the red-tint chip "Overdue · Sep 18"; Overdue is never stored and the C2 registry knows only `open` and `done` (SHL-17d).
- **AC-24** *When* Marcus clicks the ring, *then* the to-do completes optimistically, the olive disc crossfades in and the toast "To-do done · Undo" appears; Undo calls only `POST /v1/todos/{id}/reopen`, and both actions are audited (DEC-24).
- **AC-25** *Given* a done to-do, *then* it shows "✓ Done by ‹person› · ‹date›" and "Reopen" (SHL-17e).
- **AC-26** *When* the creator, the assignee or a manager-or-above confirms "Delete…", *then* the to-do is soft-deleted (hidden from lists and counts, never hard-deleted) and AUD-29 shows a "To-do deleted" entry; anyone else gets 403.
- **AC-27** *Given* "Move to another row…", *then* the to-do can be re-anchored only within the same engagement (422 `anchor_scope_mismatch` otherwise) and `todo.moved` is audited.
- **AC-28** *Given* a firm-scope to-do (no engagement, e.g. J27's "Update skill BH-SK-410"), *then* only its creator and its assignee can read it.

### 3.8 My to-dos (SHL-17f; HOME-01i)

- **AC-29** *Given* Marcus at E0 (Mon Sep 14, 2026, 12:40 PM CT), *then* My to-dos shows "Open 4 · Done", bands OVERDUE 1 (Sep 11, from HL), TODAY 1 (created by you), THIS WEEK 2 (Sep 16 from MO with an unread dot; Sep 18 from HL), and the footer "4 open · Northwind PY2025"; 1 + 1 + 2 = 4 is a golden seed test, and HOME-01's To-dos band and the C-27 chips read the same query.
- **AC-30** *Then* to-dos never appear in the HOME-02 "Waiting on you" queue or the `human_gates` projection (C13), are never client-visible, and never block a sign-off (AC-15).

### 3.9 Engagement activity log (AUD-29)

*As the EQR, I want to filter to agent actions and open the exact run trace behind any event before I concur.*

- **AC-31** *Given* Hannah on the Northwind cockpit rail Overview › Activity at Mon Sep 14, 2026, 2:30 PM, *then* 23 events since Aug 19 appear newest first with day separators TODAY, SEP 11, SEP 10, SEP 8, SEP 1, AUGUST; sign-offs, approvals and decisions carry the dark check mark, system and agent events their glyph; agent rows end " · via Agent" with the atom glyph (AUD-29a).
- **AC-32** *Then* the segmented control reads All 23 · Human 12 · via Agent 11 · Policy 0 and always foots under any Type, Date or search filter; Policy shows "No policy acceptances." / "Policy acceptance is off for Brightwater Hale (Firm settings › AI policy)." (AUD-29b–d). Classification: `via Agent` = actor kind `agent`, or `system` with an agent run; `Policy` = actor kind `policy`; everything else (people, client and third-party principals, gate facts) = `Human`.
- **AC-33** *Then* no approval, decision, sign-off, acceptance, release or send appears with an agent actor; the projection raises a build-failing INV-1 alarm if a decision-class action ever carries actor kind `agent` (INV-1).
- **AC-34** *Given* the 11:20 AM clock, *when* Hannah searches "Materiality", *then* three rows return: 11:12 "Materiality decided by Margaret Okonkwo", 9:27 "Materiality proposed · Marcus Delaney via Agent", and 11:20 "Run resumed · Marcus Delaney via Agent" matched in its detail (AUD-29e). The search text travels in the request body and is never logged or put in the URL.
- **AC-35** *Given* a row, *then* hover shows "Open" (AUD-29f) and the click routes by kind: run, draft and resume → WB-09 run trace; sign-off → AUD-06 with the signed cells lit; materiality → AUD-07 at that version; document → AUD-03 with the file in the viewer; risk → AUD-08 drawer at that version; gates → ENG-02 or CLI-07; to-do → SHL-17. A target that is not yet built is a registered planned link (no dead click).
- **AC-36** *Then* AUD-29 is readable by the engagement team (partner, manager, senior, staff, specialist, EQR, QC reviewer) and by practice leaders and quality partners in scope; firm admins and client roles are refused; senior and staff gain no access to ADM-07 (`audit_event.read` is unchanged); a walled user gets the not-allowed state (INV-3, INV-4).
- **AC-37** *Then* no edit or delete affordance or endpoint exists for events; events of an archived or locked engagement stay readable.

### 3.10 Export (AUD-29 Download)

- **AC-38** *Given* `allowed_actions` contains `export.create` (engagement partner, manager), *then* Download is shown; it requires a fresh MFA step-up; the CSV holds exactly the filtered rows with masked values as on screen and never a Restricted value (DEC-60), cells beginning `=`, `+`, `-` or `@` are neutralised against formula injection, and `audit_event.exported` records the filter hash and row count. Others never see the icon.

### 3.11 The window and the live path

- **AC-39** *Given* both flags off, *then* every new surface renders its designed flag-off state, every new route answers the P-36 flag-off error, and the SPEC-032 request-item comment suite (`apps/web/src/screens/spec032comments.test.tsx` and the TASK-062 backend tests) passes unchanged.

## 4. Contract
Endpoints, errors and payloads: `docs/plan/epics/P-05.md` §4.3, frozen into
`docs/contracts/collaboration.md` by P-05-T03. Tables: §4.2 (P-05-T04, one expand-only migration).
Matrix: §4.4 (P-05-T02). Outbox events §4.6, audit events §4.7, notifications §4.8, flags §4.9
(`collaboration.v2`, `audit_trail.engagement_activity`; boolean, default off, expiring Mon Apr 24,
2028).

## 5. Screens
`docs/screens/SHL-17.md`, `docs/screens/SHL-18.md`, `docs/screens/AUD-29.md`.

## 6. Out of scope
Attachments in the composer (OQ-8), thread-resolved notices and comment digests, client-side
notifications, any agent capability (`todo.propose` arrives with W-02), migrating the SPEC-032
tables (CL-1, first train after Apr 20, 2028).
