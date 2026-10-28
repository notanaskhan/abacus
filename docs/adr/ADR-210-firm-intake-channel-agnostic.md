---
id: ADR-210
title: Firm intake is channel-agnostic, read by an intake scope, and filed only by people (P-60 part 1)
status: accepted
date: 2026-10-27
deciders: ayushkbhatia (solo edition, AMENDMENT-solo)
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
DEC-75 asks for a firm intake mailbox (W6). Chapter 01 places the mailbox integration (Microsoft Graph ingest, subscriptions, send-as) in N-03 (S56–S62), but N-01 (S13–S18) builds the inbox, triage and files that the mailbox feeds. Without a binding rule now, N-01 would either wait three years for the mailbox or build intake shaped around one channel. DEC-20 also leaves open how a firm admin who is not on any engagement may read client documents that have not been filed yet. N-01 §11.2 OQ-1 recommends splitting P-60: part 1 (this ADR) for the channel-agnostic intake, the intake scope, visibility and hostile content; part 2 in N-03 for Graph ingest and send-as.

## Decision
1. **One intake model, many channels.** Every document that arrives outside a request is an `inbound_message` on an `inbox_thread` with `inbox_attachments`, whatever its channel: `portal_upload`, `staff_logged` or `email`. Channels write through one function, `communications.api.record_inbound_message`. A mailbox adapter is a registered inbound transport (`communications.api.register_inbound_transport`), added by N-03 under part 2; no part of triage, filing or the Files browser knows which channel a file came from beyond the `channel` value.
2. **The intake scope.** A firm-level scope held by members of a team of kind `intake` (organisations) and read by the matrix condition `intake_scope` (identity, registered through a slot; fails closed when unregistered). It may read inbound messages and attachments **until they are filed**, and may file only into non-walled, non-archived destinations of the matched client. It never reads filed evidence or workpapers through this scope.
3. **Visibility.** An unmatched thread is visible only to the intake scope, and only by sender and subject. Once matched to a client, a thread is also visible through scope kind `client` to people who can read content on at least one non-walled engagement of that client. Message bodies and attachment content need `inbox.read_content`. Walls answer 404 and no count reveals a hidden item (DEC-43).
4. **Hostile content.** Attachment bytes, file names, portal notes, staff notes and email bodies are untrusted (ADR-052). Every file is scanned before storage and every intake path fails closed when the scanner is unavailable (P-64). Parsing runs in the isolated child (ADR-110). The matcher receives intake content only as `untrusted_inputs`.
5. **People file.** `inbox.file`, `inbox.triage`, `inbox.match_sender`, `inbox.ask_client`, `inbox.log_intake` and `inbox_sender_rule.create` deny `agent` and `system`. Triage decisions are insert-only rows with `CHECK (actor_kind = 'human')`. The agent may propose a destination; it never files, ignores, holds or matches (ADR-005).
6. **Client-facing messages are templates.** Hold and Ignore notices to a client are database templates sent through a single-use approval grant after a 10-second Undo window (DEC-24); no model text reaches a client (DEC-79).
7. **Reserved for part 2 (N-03):** Graph ingest of a firm mailbox, change subscriptions, send-as and reply, `.eml`/`.msg` import, the W6 registry entry. Until part 2, `email` messages exist only on the synthetic tenant, written by the scenario loader.

## Options considered
### Option A: Split P-60, channel-agnostic part 1 now — chosen
- Pros: N-01 builds on a stable model; N-03 only adds an adapter; the intake scope and visibility are settled before any real data.
- Cons: two ADRs to read for the whole mailbox story.

### Option B: One P-60 ADR drafted in N-03
- Pros: one document.
- Cons: N-01 would build without a binding rule for the intake scope and visibility.
- Why rejected: N-01 ships three years before N-03.

### Option C: Portal-only intake, no staff-logged channel
- Pros: smaller.
- Cons: post, fax and in-person documents stay outside the trail.
- Why rejected: the pilot firms receive paper during the season.

## Consequences
**Positive**
- Every received document has an owner, a trail and a person's decision.
- N-03's mailbox is an adapter, not a redesign.

**Negative**
- The intake scope is a second way to read unfiled client content; it is bounded to unfiled items and audited on every read.

**Follow-ups**
- N-01-T02 adds the matrix rows, flags and error codes; T07 the tables; T08 the team kind and condition.
- P-60 part 2 is drafted in N-03.

## References
- `docs/plan/epics/N-01.md` §0.1, §3.9, §4.4, §11.2 OQ-1, OQ-2
- SPEC-380; DEC-20, DEC-24, DEC-43, DEC-75, DEC-79
- ADR-005, ADR-052, ADR-110, ADR-147, ADR-158
