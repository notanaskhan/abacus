---
id: ADR-241
title: "Search in Postgres: a metadata-only search_documents projection with tsvector and pg_trgm, filtered under RLS and visible() at query time, with no hidden-by-wall counts"
status: accepted
date: 2026-11-12
deciders: ayushkbhatia  # solo edition; acceptance is his (amber ADRs never default on silence)
risk_zone: amber
proposal: P-33
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

**Status note.** Drafted by P-02-T15 (TASK-7501) from chapter 09 P-33, DEC-42, DEC-43 and DF-14.
The plan calls this proposal ADR-211; that number is a P-ID alias (`docs/adr/backlog.md`), and the
S34 to S37 kickoffs reserved ADR-238 to ADR-240, so it takes ADR-241. The P-02 epic (§0.1) needs it
accepted before the C15 v1 stub (P-02-T01) merges; S39 built only what is dark and reversible
(the stub behind `search.palette`, default off, and the expand-only migration 0840). **Accepted on
2026-11-12** by ayushkbhatia (DEC-4529), after the S39 batch merged: P-02's live rows (the
indexer, the query and the palette) build on it, and it is binding from here.

## Context
Firm staff move between clients, returns, audits, binders, files, inbox threads and to-dos all
day. SHL-02 ("Go…", ⌘K) designs one grouped result list over all of them. Three facts constrain
how it may work:

1. **Walls and need-to-know are absolute.** A walled person must learn nothing about the walled
   client: not a row, not a count, not a suggestion, not a footer note (DEC-43 chose 404
   semantics everywhere; DF-14 removed SHL-02e's "2 results hidden by an ethical wall" copy).
   Walls change at any moment, and a wall added at 10:00:00 must bite at 10:00:01.
2. **Search text is sensitive.** A query is often a client's name. It must never reach a URL, a
   log line, a trace attribute, a metric label, an error report or an audit event.
3. **The index must not become a second copy of client content.** Tax return information (§7216),
   TINs and document text already have owners, retention rules and access paths; a search index
   that held them would need all of those again.

The F-03 slot (F-03-T08, `platform.slots.register_search_projection(object_type, builder)`) gave
each module a builder hook but no table, query or contract. Chapter 03 §8 and decision D-11 name
Postgres. Nothing in the ADRs covers search (chapter 09 P-33).

## Decision
1. **Postgres, no search service.** Record search is Postgres full-text search plus trigram
   similarity: a `tsvector` (config `simple`, weights title A, identifiers B, related names C,
   context D) and `pg_trgm` GIN indexes on the title, identifiers and related names. No
   OpenSearch, no Elasticsearch, no hosted search. `pg_trgm` and `btree_gin` are already created
   by `backend/migrations/bootstrap.sql` (DEC-16).
2. **pgvector is not used for records.** Embeddings stay for knowledge (ADR-053). A record search
   is lexical; it never calls a model and never touches `ai_gateway`.
3. **One projection table, owned by `platform`.** `search_documents` holds one row per
   `(tenant_id, object_type, object_id)` with forced row-level security on `tenant_id`
   (ADR-014). It is an upserted projection, not a record: it is rebuilt from the owners' current
   state and can be dropped and rebuilt from scratch by a batch workflow at any time.
4. **Metadata only.** A document carries a title, a short context line, record identifiers
   (`BH-FS-430`, `2025I:FeldJ:V3`), related party names with their labels, a status code, a due
   date and the identifiers its target route needs. It never holds a TIN (not even the last four),
   an amount, document text, a comment or review-note body, or anything Restricted. Client-supplied
   strings (file names, email subjects) are untrusted (ADR-052): SSN, EIN and ITIN patterns are
   masked and bidi and control characters are made inert before they are stored. A document's
   `data_class` is `internal`, `confidential` or `tri`.
5. **Visibility at query time, never in the index.** Each document names its `scope_kind`
   (`engagement`, `work_item`, `client`, `client_entity`, `firm`, `own`) and the scope ids. Every
   group is filtered by the same read action and scope kind as the screen it opens, through
   `visible()` (ADR-027, P-06) on the document's columns, so a result never 404s when opened.
   Walls are evaluated on `client_id` in the same predicate. Where a read action's conditions
   cannot be expressed in SQL (consent, `mfa_recent`), the service post-filters a bounded candidate
   set with `authorise()`. A `tri` document additionally needs the offshore-disclosure consent for
   an offshore member (§7216).
6. **No hidden-by-wall signal.** The API has no `hidden_by_wall` field and no count, suggestion,
   ranking signal or timing branch derived from a row the viewer cannot see. `total_visible`
   counts only what the same predicates would list, capped at 99. The did-you-mean suggestion is
   computed only from visible documents. A walled person's results for the walled client are the
   results for a client that does not exist.
7. **Search text travels only in a POST body.** `POST /v1/search` takes `{q, types?,
   limit_per_group, context?}`; there is no GET search. Query text is never logged, hashed,
   stored, traced, put in a metric label or an error, and never audited (a hash of a short client
   name is open to a dictionary attack). The statement runs with `statement_timeout = 1s`.
8. **Recents are operational state.** `search_recents` keeps a person's last 20 opened records
   as identifiers only (`own` scope, forced RLS), written only after the server re-authorises the
   object's read action, and re-filtered by `visible()` at read time, so a record walled or
   withdrawn since drops out silently. Recents are not audited (P-02 OQ-1), on the precedent of
   `kernel/slots.py`; the reindex itself is audited (`search_index.reindex_requested`,
   `search_index.reindex_completed`).
9. **Registration is the C15 contract.** Each module makes its objects findable by registering a
   `SearchProjection` in its own `api.py`: `object_type`, `group` (one canonical group), a
   `read_action` that is a read in the matrix, a `scope_kind`, a `data_class`, the events that
   reindex it, a builder `build(tenant, id) -> SearchDocument | None` and its target screen.
   Registration fails closed at boot on an unknown group, a non-read action or an unknown scope
   kind. C15 v0 builders (`register_search_projection(object_type, builder)`) keep working through
   an adapter for one sprint after v1 freezes.
10. **Who may search.** `search.read` and `search_recent.record` are firm-role actions. Client
    principals, the agent principal, system principals and `platform_support_content` sessions are
    refused: agents read through their own registered tools (C17), never the palette index, and
    the portal bundle carries no palette code (INV-4). The palette never starts an agent run;
    agent mode only opens a Workbench session for a human to send (INV-1).

## Consequences
- Every later module (C-01 closes, W-02 sessions, W-03 saved prompts, N-03 actions) adds search
  with one file and one line in its `api.py`, and the shared "every result opens" property test
  covers it with no platform change.
- The index lags its sources by the outbox relay (target p95 ≤ 5 s); a nightly drift check samples
  1% per type and a reindex workflow rebuilds a tenant on demand.
- Search quality is lexical: no semantic match, no synonyms beyond trigram similarity. That is
  accepted for record lookup; knowledge search keeps pgvector.
- One Postgres cluster carries the index. P-02-T13's load test sizes it at one million documents
  per tenant cluster with a first-group p95 ≤ 250 ms.

## Alternatives considered
- **OpenSearch or a hosted search service.** Rejected: a second store of client metadata outside
  RLS, a second place to evaluate walls (or walls baked into the index, which breaks decision 5),
  and new infrastructure and a new subprocessor.
- **Walls baked into the index (per-user or per-group ACL columns).** Rejected: a wall added now
  would leak until a reindex, and per-user rows multiply the index.
- **A "results hidden" note for admins (the original SHL-02e).** Rejected by DEC-43 and DF-14: a
  count is disclosure.
- **pgvector semantic search over records.** Rejected: needs a model call per query or per
  document, and embeddings of client names are a second copy of client data.
- **`cmdk` for the palette.** Rejected by DEC-16: Radix Dialog and a listbox (chapter 04 §5.3).
