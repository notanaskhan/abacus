# Knowledge catalog provider slot (v1)

| Field | Value |
|---|---|
| Register row | proposed for the register (K-01 §8.2; chapter 01 owns the numbering) |
| Version | v1 |
| Status | live behind the flag (K-01-T03, 2026-10-27); stubbed K-01-T01 |
| Provider epic | K-01 |
| Consumers | KNW-01; providers K-02 (firm standards), K-03 (engagement templates), K-05 (skills, notes, content packs), X-01 (frameworks), T-09 (research, templates), W-03 (agent instructions); usage counters from T-03 and C-01 |
| Freeze sprint | S11 Contract Monday (Mon Mar 22, 2027) |
| Flag | `knowledge.catalog` (default off, expires 2027-04-21, DEC-137) |
| Spec | `docs/plan/epics/K-01.md` §3.1, §4.3, §8.2 |
| ADRs | ADR-140 (module pre-registration), ADR-160 clause 11 (the approval gate), DEC-406 |

## 1. Purpose
KNW-01 lists every kind of firm knowledge in one catalog without the catalog knowing each kind. Each owning module registers a catalog provider for its category, and optionally a usage counter for its object type; the catalog composes cards, the review queue and the change log from them. Fail closed: an unregistered category shows nothing, a provider that raises shows nothing for its category.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Catalog cards | `GET /v1/knowledge/items?category=&status=&q=&cursor=&limit=` | `knowledge.read` | as `agents.yaml` (firm roles; platform content support) | denied |
| Review queue | `GET /v1/knowledge/review-queue` | `knowledge.read` | as above | denied |
| Change log | `GET /v1/knowledge/change-log?cursor=&limit=` | `knowledge.read` | as above | denied |

A client principal answers 404 (INV-4); then `knowledge.read` at the firm (403); with the flag off every route answers 404.

**The slot (K-01-T03, `methodology.api`; DEC-571):** `register_catalog_provider(category, CatalogProvider(items, review_queue, change_log))`, each `(viewer) -> rows`, where `viewer` carries the context and whether the reader manages or approves content (`methodology.manage` or `methodology.approve`, read without the fresh factor): the provider applies its own read rules (drafts only to those readers). `register_usage_counter(object_type, counter)`: `counter(ctx, ids) -> {id: n}` over `visible()`, so a walled engagement is never counted (INV-3). Registration happens in the owner's `api.py`; `methodology` imports none of them. Fail closed: an unknown category or a second provider is refused at registration; a provider that raises is left out of that response (no cards, no facet), a counter that raises leaves `usage_count` null. Registered today: `methodology` and `pbc_templates` (methodology's own; a template with a `family` is Methodology, one without a PBC template) and the usage counter `methodology_version` (engagements: engagements pinned to the version, `engagement.read_metadata` through `visible()`).

**Cards (the counting rule, AC1.4).** A provider lists its cards with their current status: for methodology, every published version (Published) and superseded version (Superseded); a template with neither has one Draft card, its newest draft, parsing or needs-review version. A draft under a published card is not a card but a review-queue row. `counts` (the status Picker) count cards per status over the category and search filters; `facets.category` (the CategoryList) count cards per **registered** category over the status and search filters: an unregistered category is absent, which the client renders as no count (`count: null`), never 0. Readers who neither manage nor approve never receive a Draft card, a review-queue row or a change-log entry of a version that is not published or superseded (AC1.6, at the API).

**Search.** Lexical and case-folded over the title, the subtitle and the provider's keywords (area names); `match[]` are the title's occurrences, [start, end).

**Routes.** Methodology published or superseded `/knowledge/methodology/{version_id}/programs` (KNW-03), otherwise `/knowledge/methodology/{version_id}` (KNW-02); a PBC template `/knowledge/templates/{version_id}` (KNW-05). Planned targets are hidden by the client (AC1.8).

**Review queue.** Versions in `needs_review` the viewer may approve, and the viewer's own draft, parsing or needs-review versions. **Change log.** `methodology_version_events`, oldest first (newest last), keyset-paged; `actor.name` is the person who acted; `facts` keep only codes, ids, counts and booleans.

## 3. Models
`backend/src/abacus/modules/methodology/contract.py`. Every field is internal (K-01 §4.2: titles and names are internal).
- **`KnowledgeItemOut`**: `id`, `category` (one of `methodology`, `pbc_templates`, `firm_standards`, `engagement_templates`, `skills`, `notes`, `content_packs`, `frameworks`, `research`, `agent_instructions`), `title`, `subtitle`, `status` (`knowledge_item`), `version_label`, `effective_from`, `owner_name`, `usage_count` (null without a counter), `usage_kind` (`engagements`, `returns`, `closes`, `audits`, `agents`: what the count counts, for its words; null with no count; K-01-T04), `updated_at`, `match[] {start, end}`, `route`.
- **`ReviewQueueItemOut`**: `category`, `object_id`, `title`, `version_label`, `status` (`methodology_version`), `submitted_by_name`, `submitted_at`, `flags_open`, `route`.
- **`ChangeLogEntryOut`**: `id`, `at`, `category`, `object_id`, `title`, `kind` (a version event kind), `actor {kind, user_id, name, on_behalf_of_user_id}`, `facts` (codes, ids and counts only).
- Lists use the P-36 envelope (`ListPage`): `counts` per status, `facets.category`.

## 4. Status words
`knowledge_item`: `draft` ("Draft"), `published` ("Published"), `superseded` ("Superseded"); `methodology_version` for the queue (`docs/product/status-vocabulary.yaml`).

## 5. Human-only actions
The catalog reads. Approving is `methodology.approve` (`methodology-programs.md`).

## 6. Errors
404 (client principal, flag off), 403 (`knowledge.read` refused), 422 `cursor_invalid`. No domain codes in v1.

## 7. Audit and outbox events
None: reads write nothing. The change log reads `methodology_version_events` (insert-only), never the audit trail.

## 8. Example payloads
Brightwater Hale (synthetic). `GET /v1/knowledge/items?category=methodology`:
```json
{"items": [{"id": "<bh-audit-methodology>", "category": "methodology", "title": "BH Audit Methodology",
            "subtitle": "EBP · FS", "status": "published", "version_label": "v3",
            "effective_from": "2026-01-01", "owner_name": "Margaret Okonkwo", "usage_count": 12,
            "updated_at": "2026-01-12T20:31:00Z", "match": [], "route": "/knowledge/methodology/<v3>"}],
 "next_cursor": null, "total": 1, "total_capped": false, "counts": {"published": 1}, "facets": {}}
```

## 9. Consumer contract tests
`backend/tests/contracts/k01_knowledge/test_k01_stubs.py`: routes, actions, flag gates, client 404, classification. `backend/tests/unit/methodology/test_k01t03_catalog_slots.py` (fail closed, ranges) and `backend/tests/integration/backfill/test_k01t03_knowledge_catalog.py` (the acceptance: cards, facets, walls, drafts, change log).

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S11, 2027-03-22) | — | stubbed 2026-10-26 (K-01-T01); live 2026-10-27 (K-01-T03) |

## 11. Open points
DEC-406 records the matrix and stub choices.
