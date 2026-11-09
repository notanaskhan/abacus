---
id: ADR-236
title: "Generalised comments: polymorphic version-aware anchors in collaboration, Resolve and Reopen as thread events, Correct and Redact, never edit or delete (amends ADR-109)"
status: proposed
date: 2026-11-09
deciders: ayushkbhatia  # solo edition; acceptance is his (red ADRs never default on silence)
risk_zone: red
proposal: P-42
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by P-05-T17 (TASK-6501) from chapter 09 P-42, DEC-29 and DF-18. The plan
calls this proposal ADR-209; that number is a P-ID alias (`docs/adr/backlog.md`), so it takes the
next free number on `main`. Until it is accepted, P-05 builds only what is reversible and dark: the
SPEC, the protected bundle, 501 stubs and an expand-only migration (S33). The comments v2 service
(P-05-T05, S34) starts only after acceptance (P-05 §11.1 R-2).

## Context
ADR-109 made comments append-only, pinned to a version and internal unless shared, but anchored
them to request items and evidence versions only, owned by `requests`, with no way to close a
thread (SPEC-032 Q7: "Threads stay open"). The 2027 designs put comments on workpaper rows and
cells (AUD-09), statement lines (FSP-01), sheet rows (SHT-01) and component work (AUD-17 via
A-09), and SHL-18 draws Resolve, Reopen, Edit and Delete. DEC-29 chose to stay append-only;
DF-18 replaced Edit and Delete in SHL-18's ··· menu with Correct… and Redact…. A comment is not a
review note: it never blocks a sign-off (R7, C3).

## Decision
1. **Owner.** Comments v2 live in the `collaboration` module: `comment_threads`,
   `comment_thread_events`, `thread_comments`, `thread_comment_mentions`,
   `thread_comment_redactions` and `comment_thread_reads`. The SPEC-032 tables (`comments`,
   `comment_mentions`, `comment_redactions`, `comment_reads`, migration 0048) stay live and
   unchanged on the request and evidence paths until the consolidation ticket CL-1 (first train
   after Apr 20, 2028) moves them with ids and sealed bytes preserved. Until then the v2 body tables
   are named `thread_*`.
2. **Polymorphic anchors through a registry.** A thread's anchor is `(anchor_kind, anchor_id,
   anchor_locator)`. Each kind is registered by its owning module through
   `collaboration.api.register_anchor(kind, provider)`; the provider answers `AnchorFacts`
   (engagement, work item, client, label, `client_visible`, current version, locator schema,
   version policy) and authorises the caller's read of the anchor. An unregistered kind answers
   409 `anchor_kind_not_registered` and writes nothing (fail closed). During the 2028 window
   `request_item` and `evidence_version` are not registered for v2, so the two stores never hold
   threads on the same anchor.
3. **Version-aware, as DEC-29 requires.** Every thread records the anchor's version when it opened
   (`opened_on_version_no`). The provider chooses the policy: `pin` keeps the thread on that
   version and a later version starts its own thread (evidence versions, as ADR-109), while
   `follow` keeps one thread per row key across versions and shows the version it opened on
   (workpaper rows and cells). Uniqueness is one thread per anchor and normalised locator, and per
   version only under `pin`.
4. **Append-only, no edit or delete.** `thread_comments`, `thread_comment_mentions`,
   `thread_comment_redactions` and `comment_thread_events` are insert-only for the app role (grants
   and triggers). There is no edit and no delete route, affordance or event.
5. **Resolve and Reopen are thread events.** Each writes a `comment_thread_events` row (`resolved`
   or `reopened`, the actor named, `actor_kind = 'human'` by CHECK) in the same unit of work as the
   `status` projection on `comment_threads`, the only thread columns the app may update besides
   visibility and timestamps. Mute, read, share and conversion are events or per-person read rows in
   the same way. Resolving never changes any gate or sign-off precondition.
6. **Correct… replaces Edit.** Only the author may post a correction: a new comment in the same
   thread with `corrects_comment_id`; the original stays and shows "Corrected below".
7. **Redact… replaces Delete.** A firm administrator holding `comment.redact`, with a fresh MFA
   step-up and a reason of 1 to 500 characters, writes one `thread_comment_redactions` row per
   comment. Every reader then sees "Redacted by ‹person› on ‹date›: ‹reason›"; the sealed body is
   kept (retention, legal hold) and never returned. Nothing is deleted.
8. **Classification and sealing.** Bodies are Restricted (ADR-031), sealed with `kernel.crypto`,
   fingerprinted, never logged and never carried by an event, notification or email (DEC-61:
   identifiers and the anchor label only).
9. **Visibility.** A firm thread is internal. Sharing is allowed only when the provider reports
   `client_visible = true` and a grant scope covers the anchor (C5); it records a `shared` event and
   firm text then passes `communications.api.check_scope`. A client principal never receives an
   internal thread from any route (INV-4). A client author may post only on a shared thread.
   Component auditors and clients join threads through scoped grants, never by membership.
10. **The agent never comments.** No model reads or writes comments (ADR-052); every `comment.*`
   action is `agent: deny`. Converting a thread into a review note is a person's action through C3,
   in the same unit of work, and only that review note blocks a sign-off.

## Consequences
- ADR-109 still binds its tables and paths. This ADR amends its anchor list and ownership and adds
  Resolve and Reopen; its append-only, version and redaction rules carry over unchanged.
- SPEC-032 Q7 ("resolving threads: not in v1") is superseded for v2 threads only; request-item
  threads keep no resolve until CL-1.
- Two comment stores coexist for one season (P-05 §11.1 R-4): distinct table names, distinct event
  names (`mention.created` for v2, the live `comment.mentioned` for SPEC-032), and v2 refuses the
  two live anchor kinds.
- Every host epic that wants comments registers an anchor provider in its own module; no host edits
  `collaboration`.

## Options considered
### Option A: append-only threads with Resolve and Reopen events, Correct and Redact — chosen
- Pros: keeps ADR-109's trustworthy record ("which wording did the client see?" never arises);
  meets SHL-18's Resolve and Reopen; Correct and Redact cover the real needs behind Edit and Delete.
- Cons: typos stay, with a correction beside them; two stores until CL-1.

### Option B: supersede ADR-109 and allow edit and delete (DEC-29 option a)
- Why rejected: an audit file's discussion must show what was said and when; history tables make
  "which version did the reviewer read?" a question on every thread.

### Option C: keep comments in `requests` and widen its anchor column
- Why rejected: puts workpaper, statement and component anchors inside the requests module, which
  may not import those modules, and edits a live path inside the 2028 busy-season window (P-29).

## Related
ADR-004, ADR-005, ADR-031, ADR-052, ADR-109, ADR-110, ADR-145 (P-06, `visible()`), ADR-160 (P-07,
review grammar), ADR-161 (P-35, Undo), ADR-232 (P-15, SSE), DEC-29, DF-18, DEC-43, DEC-61, DEC-67.
