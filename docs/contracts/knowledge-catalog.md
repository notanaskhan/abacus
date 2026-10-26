# Knowledge catalog provider slot (v1)

| Field | Value |
|---|---|
| Register row | proposed for the register (K-01 §8.2; chapter 01 owns the numbering) |
| Version | v1 |
| Status | stub (K-01-T01, 2026-10-26) |
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

A client principal answers 404 (INV-4); with the flag off every route answers 404; on, 501 `not_implemented` until K-01-T03.

**The slot (K-01-T03, `methodology.api`):** `register_catalog_provider(category, provider)` with `items(ctx, filters)`, `review_queue(ctx)` and `change_log(ctx, cursor)`, each applying the owner's read authorisation and `visible()`; `register_usage_counter(object_type, counter)` returning counts over `visible()`. Registration happens in the owner's `api.py`; `methodology` imports none of them.

## 3. Models
`backend/src/abacus/modules/methodology/contract.py`. Every field is internal (K-01 §4.2: titles and names are internal).
- **`KnowledgeItemOut`**: `id`, `category` (one of `methodology`, `pbc_templates`, `firm_standards`, `engagement_templates`, `skills`, `notes`, `content_packs`, `frameworks`, `research`, `agent_instructions`), `title`, `subtitle`, `status` (`knowledge_item`), `version_label`, `effective_from`, `owner_name`, `usage_count` (null without a counter), `updated_at`, `match[] {start, end}`, `route`.
- **`ReviewQueueItemOut`**: `category`, `object_id`, `title`, `version_label`, `status` (`methodology_version`), `submitted_by_name`, `submitted_at`, `flags_open`, `route`.
- **`ChangeLogEntryOut`**: `id`, `at`, `category`, `object_id`, `title`, `kind` (a version event kind), `actor {kind, user_id, name, on_behalf_of_user_id}`, `facts` (codes, ids and counts only).
- Lists use the P-36 envelope (`ListPage`): `counts` per status, `facets.category`.

## 4. Status words
`knowledge_item`: `draft` ("Draft"), `published` ("Published"), `superseded` ("Superseded"); `methodology_version` for the queue (`docs/product/status-vocabulary.yaml`).

## 5. Human-only actions
The catalog reads. Approving is `methodology.approve` (`methodology-programs.md`).

## 6. Errors
404 (client principal, flag off), 501 until K-01-T03. No domain codes in v1.

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
`backend/tests/contracts/k01_knowledge/test_k01_stubs.py`: routes, actions, flag gates, client 404, classification.

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S11, 2027-03-22) | — | stubbed 2026-10-26 (K-01-T01) |

## 11. Open points
DEC-406 records the matrix and stub choices.
