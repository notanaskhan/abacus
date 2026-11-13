---
id: RB-82
title: Search index drift, lag and rebuild (C15)
owner: builder
owning_epic: P-02
alarms: [abacus-staging-search-index-lag-p95]
last_rehearsed: never
rehearse_by: 2027-01-29
---
# RB-82 · Search index drift, lag and rebuild

| Field | Value |
|---|---|
| Owner | builder (P-02-T14; DEC-4727). P-02's plan called this "proposed RB-31"; RB-31 was already the notification email pause, so it takes the next free number |
| Severity range | SEV3 (results trail or miss their records); SEV1 if a walled or other firm's record is ever returned (then RB-08 first) |
| Linked from | `abacus-staging-search-index-lag-p95` (`infra/envs/staging/search.tf`); `backend/src/abacus/modules/platform/README.md` (Search) |
| SLO affected | relay lag p95 ≤ 5 s; first-group p95 ≤ 250 ms (P-02 exit) |
| Kill switches that apply | `search.palette` per firm (off: the palette and routes answer 404; the indexer keeps running) |
| Related | RB-08 (cross-firm exposure), RB-13 (offboarding purge), RB-28 (realtime delivery, the same relay) |

The index (`search_documents`) is a rebuildable projection: every row can be rebuilt from its
owner's builder, and nothing in it is a record of its own. Walls are applied at query time, so a
wall never needs a reindex. Search text is never in any log; do not add it to diagnose.

## 1. Recognise it
- The lag alarm: `SearchIndexLagMs` p95 over 5 s for 15 minutes (the indexer's `search.index_lag`
  lines, relay path only).
- `abacus.search.drift` above zero in the nightly drift check (sampled rows whose stored hash
  differs from the builder's), or a `search.drift_failed` line naming a firm.
- A person reports a renamed client or a new record that the palette does not find, or finds
  under its old name, more than a minute after the change.
- A `search.document_refused` line: a builder produced a document the contract refuses (logged
  by type and id only); that row is deleted rather than left stale.

## 2. Contain
- **A walled or other firm's record returned?** That is not drift: RB-08 §1–3 now, and turn
  `search.palette` off for the firm while it is assessed.
- **Lag only:** results trail but are correct. No containment; the relay catches up. If the relay
  itself is stuck (RB-28's signals also firing), work RB-28 first.
- **Wrong or missing rows for one firm:** leave the palette on (it filters on current
  permissions at query time) and rebuild (§6).

## 3. Preserve
Nothing to preserve: the index is derived. Note the alarm window, the firm ids and the object
types from the `search.index_lag` / `search.drift_failed` lines (identifiers only).

## 4. Assess
- Lag: `search.index_lag` by `object_type` over the alarm window. One type high: its builder is
  slow (an owner query) or a fan-out over 200 ids went to the reindex workflow. All types high:
  the relay or the database (RB-28, RDS connections).
- Drift: run the check for the firm now, `python -m abacus_tools.search drift <tenant>`; the count
  is the sampled rows that differed and were rebuilt. A recurring count for one type means its
  triggers miss an event: a code fix in the owning module, recorded as an escaped defect.
- Speed: first-group p95 regressed? The plan guard (`test_p02t13_search_plan_guard.py`) and the 1M
  load test (`python -m abacus_tools.loadtest.search`) say whether a predicate stopped being
  index-served.

## 5. Notify
No client notice: the index holds metadata only and drift exposes nothing. Tell the firm's
contact only if search was turned off for them (§2).

## 6. Recover
- One record: `python -m abacus_tools.search index <tenant> <type> <id>` (inline; the row is
  derived, so no audit event).
- One type or one client: `python -m abacus_tools.search reindex <tenant> --type <type>` or
  `--client <client_id>` (starts or joins `search_reindex:<tenant>:…`, audited
  `search_index.reindex_requested` / `.reindex_completed`).
- Whole firm: `python -m abacus_tools.search reindex <tenant>`. Pages of 500, each rebuilt from
  current state; safe to repeat.
- A builder bug: fix it in the owning module, deploy in the batch, then reindex that type.

## 7. Verify
- The lag alarm back to OK; `search.index_lag` p95 under 5 s for the next hour.
- `python -m abacus_tools.search drift <tenant>` reports 0.
- The reported record is found under its current name, as the person who reported it.

## 8. Review
A blameless note for SEV3 and above: which trigger or builder missed, and the test that now
covers it (a builder unit test or a C15 consumer case).

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
