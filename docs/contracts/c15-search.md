# C15 v1 · Search registration and the search API

| Field | Value |
|---|---|
| Owner | `platform` (`backend/src/abacus/modules/platform/search/`) |
| Version | v1 (stub: P-02-T01, TASK-7504). Frozen at the S39 sprint review; additive changes in place, a breaking change ships as v2 with one sprint of overlap |
| Binding | ADR-241 (P-33 Search in Postgres), DEC-43 (404 semantics for walls), DF-14, ADR-027/ADR-145 (`visible()` and scope kinds), ADR-139 (error codes), ADR-031 (classification) |
| Flags | `search.palette` (routes, ⌘K, the SHL-02 mount; off: 404) · `search.agent_mode` (the `>` prefix) |
| Consumers | SHL-02 (P-02-T10); every module with findable objects; the consumer suite `backend/tests/contracts/c15_search/` and `apps/web/src/fixtures/contracts/search.contract.test.ts` (P-02-T02) |
| Status | Live behind `search.palette` since P-02-T08 (2026-11-12, DEC-4614): the query and recents services; the indexer (P-02-T06) and the seven projections (P-02-T07) fill the index |

## 1. Registration (Python, `platform.api`)

```python
from abacus.modules.platform.api import SearchProjection, SearchIndexDocument, register_search_projection

register_search_projection(SearchProjection(
    object_type="tax_return",          # snake_case, one projection per type
    group="returns",                   # one canonical group (§3)
    read_action="tax_return.read",     # a read in the permission matrix: the screen's own action
    scope_kind="engagement",           # engagement · work_item · client · client_entity · firm · own
    data_class="tri",                  # internal · confidential (default) · tri
    triggers={"work_item.status_changed": lambda p: [p["work_item_id"]]},
    build=build_tax_return_document,   # async (tenant, object_id) -> SearchIndexDocument | None
    target="TAX-02",                   # the manifest screen a row opens
    rank=10,
))
```

- **Fail closed at import.** An unknown group, a read action that is missing from the matrix or is
  not a read, an unknown scope kind or data class, a target that is not a screen id, or a trigger
  that is not an event type raises `SearchRegistrationInvalid`. The same projection registered
  twice is a no-op; a different one for a known type raises.
- **A builder returns current state or `None`.** `None` deletes the document (a withdrawn upload, a
  deleted record). Builders read only their own module's tables.
- **A document is metadata only** (`SearchIndexDocument`): `title` (1–300), `context` (≤ 300),
  `identifiers` (≤ 20 record keys), `related` (≤ 20 `RelatedParty(name, label)`), `status_code` and
  `status_context` (C2), `due_on`, `tag` and `use_count` (saved prompts), `target_params`
  (identifiers only: keys `[a-z][a-zA-Z0-9]*`, values `[A-Za-z0-9_.:-]{1,80}`), and the scope ids.
  `client_id` is required unless the scope kind is `firm` or `own`; an `engagement` or `work_item`
  document names its engagement; an `own` document its owner. **Never** a TIN (not even the last
  four), an amount, document text, a comment or review-note body, or anything Restricted.
- **v0 adapter.** `register_search_projection(object_type, builder)` (F-03-T08) still registers a
  v0 builder in `platform.slots` for one sprint after v1 freezes.

## 2. HTTP

All three routes are POST or GET under `/v1/search`, each with exactly one matrix action. Order of
refusal: the matrix (403 `forbidden`: client roles, the agent, the system, the QI and break-glass
support sessions hold neither action), then `search.palette` off (404), then the request.

| Method and path | Body or query | Response | Action | Errors |
|---|---|---|---|---|
| `POST /v1/search` | `SearchQueryIn {q, types?, limit_per_group = 5 (1–10), context?: {object_type, object_id}}` | `SearchResultsOut {groups: [{group, items, has_more}], suggestion, total_visible}` | `search.read` | 403 · 404 (flag) · 422 `q_invalid` · 429 `rate_limited` · 501 · 503 `search_unavailable` |
| `GET /v1/search/recents?limit=5` | `limit` 1–10 | `SearchRecentsOut {items}` | `search.read` | 403 · 404 (flag) · 501 |
| `POST /v1/search/recents` | `SearchRecentIn {object_type, object_id}` | `SearchRecentRecordedOut {object_type, object_id}` (200) | `search_recent.record` | 403 · 404 (flag, or the viewer may not read the object) · 501 |

- **Search text is only in the POST body.** `q` is cleaned server-side (control, format and bidi
  characters dropped, whitespace collapsed, trimmed) and must be 1–100 characters after cleaning,
  except `types: ["agents"]` with an empty `q` (agent mode, `search.agent_mode` on). It is never
  logged, traced, put in a metric label, stored, hashed or audited.
- **Item shape** `SearchItemOut`: `object_type`, `object_id`, `title`, `context`, `status {code,
  context}`, `due_on`, `tag`, `use_count`, `target {screen_id, params}`, `match_ranges [[start,
  end)]` over `title`.
- **No wall signal.** There is no `hidden_by_wall` field. `total_visible` counts only rows the same
  predicates would list, capped at 99. A group with no rows is omitted. `suggestion` is computed
  only from visible documents and sent only when every group is empty.
- `POST /v1/search` keeps working while a firm is read-only (it is a read sent as a POST); the
  recents write does not.

## 3. Groups and scope kinds

Canonical order: `clients · returns · audits · closes · binders · files · inbox · sessions · todos ·
saved_prompts`; `agents` in `>` mode only. "Actions", "Recent" and "Create" are composed by the
palette, never indexed. Each group's rows are filtered by their projection's `read_action` through
`visible()` for its `scope_kind` (walls on `client_id`), and post-filtered with `authorise()` where
the action's conditions are not expressible in SQL. A `tri` document needs the offshore-disclosure
consent for an offshore member (§7216).

## 4. Classification

Titles, context lines, related names, the suggestion and the query text are `confidential`;
identifiers, codes, dates, counts and match ranges `internal`. Nothing is Restricted.

## 5. Not in v1 (later rows)

The `search_documents` and `search_recents` tables (P-02-T05), the indexer, reindex workflow and
drift check (T06), the owners' builders (T07), the live query and recents (T08), the palette (T10).
pgvector is not used for record search (ADR-241 decision 2).
