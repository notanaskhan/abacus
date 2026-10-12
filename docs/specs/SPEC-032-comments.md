---
id: SPEC-032
title: "Comments: threads on requests and evidence versions, shared by client and firm"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-020, ADR-027, ADR-031, ADR-052, ADR-065, ADR-109]
related_specs: [SPEC-004, SPEC-006, SPEC-013, SPEC-020, SPEC-021, SPEC-031]
created: 2026-10-12
updated: 2026-10-12
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Clients and the engagement team discuss a request, or one specific evidence version, where the work is, instead of by email. Comments follow ADR-109:
- **append-only**, with corrections;
- **pinned** to the item or to the exact version;
- **internal by default** for the firm, and shared only when a team member chooses;
- **always shared** when a client writes.

**Mentions** notify the person mentioned. A firm administrator can **redact** a comment posted in error. Every comment and redaction is audited.

This is Track A4 of the Act 2 plan. No model reads or writes comments (agents reading comments is later work, under ADR-052).

## 2. Problem and context
- **The only words that pass between client and firm in the product** are SPEC-031's guidance, still-needed note and send-back note. Each is one-way and replaced when edited (the send-back note is fixed per decision). Questions ("which account do you mean?", "the bank only gives CSV, is that fine?") go to email, away from the evidence.
- **The team has nowhere to leave a note** on a file for each other ("tie this to the confirmation") except outside the product.
- **The platform already has the pieces:**
  - in-app notifications for the firm (SPEC-013: identifiers and a kind, text rendered by the SPA);
  - envelope encryption per tenant (`kernel.crypto`, used for evidence and credentials);
  - the outbound scope check (`communications.check_scope`, SPEC-006), which flags other clients' names, other ledgers' accounts and amounts not in this engagement;
  - SPEC-020's item visibility rules for client users.
- **The client portal has no notification bell.**

## 3. Actors
| Actor | Role here |
|---|---|
| Client admin, client contributor | Read shared comments on requests and versions they can see; comment (always shared); mention people who can see the item |
| Engagement partner, manager, senior, staff, reviewer | Read all comments on the engagement; comment internally or shared; mention; correct their own comments |
| Firm administrator | Redact a comment posted in error, with a reason |
| The platform (code) | Enforces visibility; checks shared firm comments for out-of-scope content (Q4); notifies mentions; audits |

## 4. Goals and non-goals
**Goals**
1. **Threads:**
   - one thread per request item, and one per evidence version on that item (ADR-109: a later version starts its own; earlier threads stay with their version);
   - comments in time order, each showing:
     - author;
     - side (firm or client);
     - when;
     - visibility (internal or shared);
     - any correction link.
2. **Writing:**
   - plain text, up to 4,000 characters;
   - a firm member chooses **Internal note** (the default) or **Share with client**;
   - a client's comment is always shared;
   - no attachments: files go through uploads (SPEC-020).
3. **Corrections:**
   - nothing is edited or deleted;
   - the author can post a correction to their own comment;
   - the original shows "Corrected below" and the correction shows "Corrects an earlier comment".
4. **Visibility:**
   - client users see shared comments only, and only on items they may see (SPEC-020: client-visible, and for contributors, assigned to them) and on those items' versions;
   - firm members see everything on engagements they may read;
   - internal notes are shown distinctly, on a different background and labelled "Internal: the client can't see this".
5. **Mentions:**
   - `@` picks from the people who may read that comment: for an internal note, the engagement team; for a shared comment, the team plus the client users who can see the item;
   - a mention creates an in-app notification for that person (SPEC-013 for the firm; the client side, Q2).
6. **Redaction (ADR-109):**
   - a firm administrator redacts a comment with a reason;
   - every reader then sees "Redacted by {name} on {date}: {reason}" in its place;
   - the redaction is audited;
   - nothing is deleted (Q5).
7. **Counts:** the Board and the client's request list show how many comments each item has (counting its versions), with unread ones marked for the reader (Q6).
8. **Storage and protection:**
   - comment text is Restricted (ADR-031), sealed per tenant with `kernel.crypto` (Q3), and never logged;
   - insert-only tables;
   - audit events carry identifiers only.

**Non-goals**
- Agents reading, summarising or writing comments (later; ADR-052 applies).
- Email delivery of comments or mentions: no transport exists yet (SPEC-006).
- Editing, deleting, reactions, rich text, attachments.
- Comments on anything but request items and evidence versions (for example engagements or samples).
- Resolving or closing threads (Q7).

## 5. User stories and acceptance criteria
**Story — Rachel asks; Priya answers; Marcus leaves a note.** Rachel, the client's controller, opens "Bank statements for December" and asks: "Our bank only exports CSV for the payroll account. Is that OK?" Priya, the senior, gets a notification, replies "Yes, a CSV export is fine", shares it with the client, and mentions Rachel. Marcus, the manager, adds an internal note on the uploaded version: "Tie the payroll CSV to the TB before accepting." Rachel never sees it.

- **AC-1** Given a request item or one of its evidence versions, then each has its own thread; a new version starts empty, and earlier threads stay with their version.
- **AC-2** Given a firm member posting, then the comment is internal unless they choose Share with client; given a client user, then it's always shared.
- **AC-3** Given a client user, then they see only shared comments, only on items (and those items' versions) they may see under SPEC-020; internal notes are never returned to them by any API.
- **AC-4** Given a posted comment, then it can't be edited or deleted; its author can post a correction, and both show the link.
- **AC-5** Given a mention, then only people who may read that comment can be mentioned, and each is notified once.
- **AC-6** Given a firm administrator, then they can redact a comment with a reason; every reader sees the redaction stub instead of the text; it's audited; others can't redact.
- **AC-7** Given a firm member sharing a comment, then the scope check runs; a violation blocks it with the reasons, and it can be posted as an internal note instead (Q4).
- **AC-8** Given the Board and the client's request list, then each item shows its comment count and whether any are unread for the reader (Q6).
- **AC-9** Given any comment, then its text is sealed at rest, never logged, and every post, correction and redaction writes an audit event with identifiers only.
- **AC-10** Given every new screen, then loading, empty, error and not-allowed states exist; internal notes are visually distinct; colours come only from tokens.

## 6. Design notes
- **Module:** a new `comments` module would need the module map and `app.py` (protected). The alternative is to place comments in `requests`, which already owns the item and its visibility. Evidence versions are reached through the item's fulfilments, which requests already reads (Q1).
- **Data:**
  - `comments` (insert-only):
    - id, tenant, engagement, request item, evidence version (nullable);
    - author user and side;
    - visibility (`internal`, `shared`);
    - the sealed body and its fingerprint;
    - `corrects_comment_id`, created_at;
  - `comment_mentions` (insert-only): comment and user;
  - `comment_redactions` (insert-only): comment, redacted by, reason (up to 500 characters), created_at;
  - `comment_reads` (upsert of a last-read time per user and thread, Q6).
- **Permissions** (new matrix actions):
  - `comment.read` (firm roles, and client roles with SPEC-020 item conditions);
  - `comment.create` (the same, with independence for the firm);
  - `comment.share` (partner, manager, senior, staff);
  - `comment.redact` (firm admin, MFA recent).
  - A client role is filtered to shared comments in the service, as SPEC-029 does for client-audience checks.
- **Notifications:** a new catalogue kind `comment.mentioned` (identifiers only; the SPA renders "{name} mentioned you on {item}").
- **API:**
  - `GET/POST …/request-items/{id}/comments`;
  - `GET/POST …/request-items/{id}/versions/{version}/comments`;
  - `POST …/comments/{id}/redact`;
  - `POST …/comments/read` (marks a thread read);
  - comment counts on the request list and the Board.
- **Web:**
  - a thread panel in item detail (item and selected version);
  - a thread under each request in the client portal, per version in its history;
  - the mention picker;
  - redaction in item detail for firm administrators.

## 7. Delivery
- **TASK-062 (red, backend):** tables and grants; the permission actions; post, correct, share with the scope check, mentions and notifications, redaction, reads and counts; tests.
- **TASK-063 (amber, web):** firm thread panel with the internal/shared distinction; the client thread; the mention picker; counts on the Board and the client list; redaction; the client portal's notifications (if Q2 says yes).

## 8. Test plan
| AC | Level | What |
|---|---|---|
| AC-1, AC-4 | unit, integration | Threads per item and version; insert-only (an UPDATE or DELETE is refused by grants); corrections |
| AC-2, AC-3 | integration | Default visibility; a client never receives internal notes from any route, or comments on items they can't see |
| AC-5 | unit, integration | Mention candidates by visibility; one notification each |
| AC-6 | integration | Redaction by role; stub shown; audited |
| AC-7 | unit | Scope check blocks a shared comment naming another client |
| AC-8 | integration | Counts and unread per reader |
| AC-9 | unit | Body sealed; log scrubbing; audit refs |
| AC-10 | vitest | States; internal styling |

## 9. Open questions
All resolved: the founder approved every recommendation below on 2026-10-12.
- **Q1 — where comments live.** *Recommendation:* in `requests`, which owns items, their client visibility and their fulfilments. A new module needs the module map, the dependency rules and `app.py` changed, all protected, for no gain yet.
- **Q2 — notifications for clients.** The client portal has no bell. *Recommendation:* add a small one to the client portal's header (the same `GET /v1/notifications`, which already scopes to the caller) in TASK-063, so a client hears about mentions and replies. *Alternative:* firm-only notifications for now.
- **Q3 — sealing the text.** *Recommendation:* seal each comment body with `kernel.crypto` (per-tenant envelope keys), as evidence and credentials are, since it is Restricted. It costs a decrypt per comment shown, which is small at thread sizes. *Alternative:* plain text protected by RLS only.
- **Q4 — the scope check on shared firm comments.** *Recommendation:* run `communications.check_scope` before a firm comment is shared. A violation (another client's name, another ledger's account, an amount not in this engagement) blocks it with the reasons, as an outbound message is blocked, and the person can keep it internal. Client comments aren't checked (they're the client's own words).
- **Q5 — what redaction does to the stored text.** ADR-109 says nothing is deleted. *Recommendation:* keep the sealed body (no route ever returns it after redaction). If a client posts a password, the firm should still rotate it. Destroying the text (for example a per-comment key) would need a new ADR, so it's out of scope here.
- **Q6 — unread.** *Recommendation:* a per-person last-read time per thread, set when the thread is opened. The Board and the client list show the count, with a dot when there's anything newer than that.
- **Q7 — resolving threads.** *Recommendation:* not in v1. Threads stay open; the request's status says where the work is.
- **Q8 — who is notified without a mention.** *Recommendation:* only mentions in v1. A client comment with no mention notifies nobody, but shows as unread on the Board. *Alternative:* notify the engagement's senior or the item's assignee on every client comment.
