---
id: SPEC-009
title: Knowledge retrieval infrastructure (pgvector), without content
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-053, ADR-056, ADR-014, ADR-019, ADR-052, ADR-031, ADR-069, ADR-073]
related_specs: [SPEC-003, SPEC-007, SPEC-008]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
This is the infrastructure for ADR-053's fourth kind of memory, *knowledge*: a firm's own methodology documents, recalled by vector search. It covers:
- **Ingestion:** a firm admin adds a document. It is split into chunks deterministically, and each chunk is embedded through `ai_gateway`.
- **Retrieval:** a firm-scoped similarity search returns attributed chunks for people and, later, for agents' context.

Phase 1 builds it "without content" (build plan §5.3). The pipeline, isolation and metering are production-depth. Populating firms' documents is Phase 5 (ADR-056).

## 2. Problem and context
Agents will need the firm's methodology: what the firm requires for cash, how it tests receivables. Today there is nowhere to put it and no way to recall it.
- **Postgres already runs with pgvector** (ADR-014), and the Python `pgvector` package is on the allowlist.
- **ADR-053 sets the rules:**
  - facts live in tables, and vectors are used only for recall;
  - every memory is attributed and scoped;
  - retrieval goes through `visible()`;
  - there is **no shared embedding index across tenants**.
- **ADR-056:** only the firm's own and publicly available material, never licensed standards without a licence.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Firm admins and practice leaders | Add and withdraw knowledge documents (Q4) |
| Firm users | Search the firm's knowledge |
| Agents (later) | Receive retrieved chunks as context through `ContextBuilder` |
| `ai_gateway` | The only path to the embedding model; budgets and metering apply |

## 4. Goals and non-goals
**Goals**
- **Documents:**
  - `knowledge_documents` and `knowledge_chunks` are tenant-scoped with forced RLS;
  - every chunk is attributed to its document, position and the embedding model that produced it.
- **Ingestion:**
  - plain text and Markdown (Q3);
  - deterministic chunking;
  - embedding through a new `ai_gateway.embed`, as batch-class work (ADR-072), metered and within budget (SPEC-007).
- **Retrieval:** `search_knowledge(ctx, query, k)`:
  - the query is embedded through the gateway (interactive class);
  - the search is exact cosine over the caller's firm only;
  - it returns the top *k* chunks with their scores and sources.
- **Isolation (ADR-053):**
  - no shared ANN index across tenants (Q1);
  - a cross-tenant test returns nothing.
- **Embedding provider:**
  - a provider-agnostic `EmbeddingProvider` behind the gateway;
  - a deterministic fake for development and CI;
  - the real provider is configured with the second model route (ADR-073, Q2).

**Non-goals**
- **Content:** loading any firm's documents (Phase 5), and licensed standards (ADR-056).
- **Formats:** PDF and DOCX extraction (they need new dependencies; Q3).
- **Other memory:** engagement and client-scoped knowledge, engagement facts, and agent-proposed memories (ADR-053; later specs).
- **Ranking:** re-ranking, hybrid keyword search and query rewriting.
- **Any UI.**

## 5. User stories and acceptance criteria
### Story 1: A firm adds its methodology
- **AC-1** Given a firm admin and a UTF-8 text or Markdown document within the limits, when they add it with a title and a source kind (`firm_own` or `public`, Q5), then in one unit of work:
  - the document is stored as `pending`, with its SHA-256 fingerprint;
  - its chunks are stored;
  - `knowledge_document.added` is audited.

  Embedding then runs as a batch-class workflow. When every chunk has a vector, the document becomes `ready`.
- **AC-2** Given a document, then chunking is deterministic: the same text always gives the same chunks. Chunks:
  - split on Markdown headings, then paragraphs;
  - are at most 1,200 characters, with a 150-character overlap only when a paragraph must be split;
  - carry the nearest heading path as context.
- **AC-3** Given a document that is too large, isn't valid UTF-8, has an unknown source kind, or would exceed the firm's limits, then nothing is stored, and the caller gets 422 with a fixed code.
- **AC-4** Given a firm admin, when they withdraw a document, then it becomes `withdrawn`, its chunks are excluded from search from that moment, and `knowledge_document.withdrawn` is audited. Purging the stored text follows the retention policy later.

### Story 2: Embedding is a model call like any other
- **AC-5** Given any embedding (ingestion or query), then it goes through `ai_gateway.embed`, which:
  - requires a tenant, a work class and a budget;
  - is checked against the budget hierarchy (SPEC-007) and admission (SPEC-003);
  - writes a usage record (`prompt_id` `embed`, the model, input tokens and cost).

  No code outside `ai_gateway` imports an embedding SDK (the existing provider ban, ADR-019).
- **AC-6** Given the embedding workflow fails part-way (a provider outage), then it resumes from the chunks without vectors. Nothing is embedded twice, and the document stays `pending` until complete. A permanent failure marks it `failed` with a fixed code.
- **AC-7** Given each chunk records its `embedding_model`, when the configured model changes, then search uses only chunks embedded with the current model. Re-embedding is deferred, and a document whose chunks are all on another model reports `stale`.

### Story 3: Recall without leaks
- **AC-8** Given a firm user with `knowledge.read` and a query of up to 1,000 characters, when they search, then they get up to *k* (at most 20) chunks:
  - each with its document ID, title, heading path, position, text and cosine score;
  - only from `ready` documents of their own firm;
  - ordered by score, with ties broken by document and position.
- **AC-9** Given two firms with similar documents, when one firm searches, then no chunk of the other firm is ever returned or scored. Isolation holds both in the query (RLS and an explicit `tenant_id` filter) and in the index design (no shared ANN index, Q1).
- **AC-10** Given retrieved chunks are placed in a model's context (later agents), then they enter as untrusted, delimited content through `ContextBuilder`, classified `internal` (ADR-052). This spec provides `knowledge_context(chunks)` for that.

## 6. Behaviour and flows
1. **Add:**
   - parse and validate;
   - chunk;
   - in one unit of work, insert the document as `pending`, insert the chunks without vectors, audit, and emit the outbox event `knowledge_document.added`;
   - the relay starts `KnowledgeEmbeddingWorkflow` (batch class).
2. **Embed:**
   - the workflow embeds chunks without vectors in batches of up to 64, through `ai_gateway.embed` attributed to the firm, and stores the vectors;
   - when no chunk lacks a vector, the document becomes `ready`.
3. **Search:**
   - embed the query (interactive class);
   - `SELECT … ORDER BY embedding <=> :q LIMIT :k` over `ready` documents' chunks with the current model, inside `tenant_session`, with `tenant_id = :tenant` explicit as well as RLS.

## 7. Domain and data changes
- **Extension:** `CREATE EXTENSION IF NOT EXISTS vector` in the migration.
- **`knowledge_documents`** (tenant-scoped, forced RLS):
  - columns: `id`, `tenant_id`, `title`, `source_kind` (`firm_own`, `public`), `media_type`, `fingerprint`, `char_count`, `status` (`pending`, `ready`, `failed`, `withdrawn`), `failure_code`, `added_by`, `created_at`, `withdrawn_at`;
  - UPDATE is granted only on `status`, `failure_code` and `withdrawn_at`;
  - unique on (`tenant_id`, `fingerprint`) among non-withdrawn documents, so the same document isn't added twice.
- **`knowledge_chunks`** (tenant-scoped, forced RLS):
  - columns: `tenant_id`, `document_id`, `position`, `heading_path`, `text` (internal), `char_count`, `embedding vector(1024)` (nullable until embedded), `embedding_model`, `embedded_at`;
  - UPDATE is granted only on `embedding`, `embedding_model` and `embedded_at`, null to value, by the workflow.
- **Indexes:** a btree on (`tenant_id`, `document_id`). **No HNSW or IVFFlat index** in v1 (Q1).
- **Settings:**
  - limits: document up to 1 MB of text, up to 2,000 chunks per document, up to 50,000 chunks per firm;
  - `embedding_model` and `embedding_dimensions` (1,024).

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `ai_gateway.embed(EmbedCall) -> EmbedResult` | The only embedding path: tenant, work class, budget, metering |
| `POST /v1/knowledge/documents` (JSON: title, source_kind, media_type, text) | Add (AC-1 to AC-3); `knowledge.manage` |
| `GET /v1/knowledge/documents` and `GET /v1/knowledge/documents/{id}` | List documents and their status; `knowledge.read` |
| `POST /v1/knowledge/documents/{id}/withdraw` | Withdraw (AC-4); `knowledge.manage` |
| `POST /v1/knowledge/search` `{query, k}` | Search (AC-8); `knowledge.read` |
| `search_knowledge(ctx, query, k)` and `knowledge_context(chunks)` | For agents (later), from the owning module's API |

## 9. Authorisation and tenancy
- **New matrix actions (a protected change):**
  - `knowledge.manage`: firm admin and practice leader, with fresh MFA;
  - `knowledge.read`: every firm role, plus engagement partner, manager, senior and staff (Q4).

  Agents read through their run's context, which comes later. Client users are never allowed.
- **Visibility:** knowledge is firm-wide in v1, so `visible()` reduces to the tenant (no engagement scope). Walls don't apply, since firm methodology names no client.

## 10. AI behaviour
- **Model:** one embedding model through the gateway. It is never asked to judge, and its output is a vector.
- **Context:** retrieved text enters later prompts only as delimited, untrusted, classified context (AC-10).
- **Evaluation:** a retrieval evaluation suite (recall@k on a synthetic methodology set) is registered with the evaluation runner, with cases added with content (Phase 5).

## 11. Integrations
The embedding provider. A fake in development and CI; the real one with ADR-073's second route (Q2).

## 12. Edge cases and failure modes
- **A provider outage during ingestion:** the workflow retries with backoff and resumes (AC-6).
- **Budget exhausted:** ingestion is deferrable, so it waits or fails `budget_exhausted` per SPEC-007. A search's query embedding is interactive.
- **Withdrawal during embedding:** the workflow stops at its next batch, and the document stays `withdrawn`.
- **A query with no ready documents:** an empty list, not an error.
- **Firm scale:** exact search over 50,000 chunks of 1,024 dimensions is about 50,000 dot products, roughly tens of milliseconds. Above the limit, Q1's per-firm partitioning is the next step.

## 13. Security and privacy
- **Classification:** chunk text is classified internal (the firm's methodology). It is never logged; logs carry IDs and counts.
- **Isolation:** the explicit tenant filter plus RLS, and no shared ANN index (ADR-053 enforcement).
- **Hostile content:** document text is treated as hostile when it is later put in prompts (ADR-052). The sanitiser (SPEC-006) applies to any model output derived from it.
- **Licensing:** `source_kind` is recorded per document. `licensed` isn't accepted in v1 (ADR-056).

## 14. Audit trail and evidence integrity
`knowledge_document.added`, `knowledge_document.withdrawn`, `knowledge_document.ready` and `knowledge_document.failed` are audited. Searches are not audited, since they return the firm's own methodology, not client content.

## 15. Observability
- **Metrics:** embedding tokens and cost (from usage records), ingestion duration, search latency, and documents by status.
- **Logs:** `knowledge.embed_batch` (counts) and `knowledge.search` (k, result count and latency; never the query).

## 16. Performance and scale
- **Search:** p95 under 300 ms at 50,000 chunks per firm, including the query embedding.
- **Ingestion:** batches of 64 chunks, batch class.

## 17. UX
None in this spec.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-4 | unit + integration | Validation, deterministic chunking (golden cases), add, withdraw, audit |
| AC-5 | unit + integration | `embed` meters, budgets and admits; provider ban |
| AC-6, AC-7 | integration | Resume after failure; model change excludes old chunks |
| AC-8, AC-9 | integration | Ranking and ties; two firms with identical text, no cross-firm hit |
| AC-10 | unit | `knowledge_context` delimits and classifies |

## 19. Rollout
No flag. The migration is additive and creates the `vector` extension. There is no content until Phase 5.

## 20. Open questions
- [ ] **Q1: index design under "no shared embedding index across tenants" (ADR-053).** *Recommendation:* no ANN index in v1. Use exact search over the firm's chunks (btree on `tenant_id`), with a cap of 50,000 chunks per firm. When a firm needs more, list-partition `knowledge_chunks` by tenant with an HNSW index per partition (a later spec). One shared HNSW index filtered by tenant would break the ADR's enforcement line, and per-firm partial indexes need DDL at onboarding.
- [ ] **Q2: the embedding provider and dimensions.** *Recommendation:* 1,024 dimensions, with a provider-agnostic `EmbeddingProvider` and a deterministic fake now. The real provider is chosen with the second model route (ADR-073, after the TASK-014 inputs). Amazon Titan Text Embeddings v2 on Bedrock (1,024 dimensions; stays in AWS) is the default candidate.
- [ ] **Q3: formats in v1.** *Recommendation:* plain text and Markdown only. PDF and DOCX extraction need new dependencies and hostile-file handling, so they come with content in Phase 5.
- [ ] **Q4: who manages and who reads.** *Recommendation:* firm admins and practice leaders manage, with fresh MFA. Every firm role and every engagement role except client users reads, because knowledge is firm-wide.
- [ ] **Q5: owner module and source kinds.** *Recommendation:*
  - the `agents` module owns the knowledge tables (ADR-053 memory sits with the agents that use it; `ai_gateway` owns only the embedding call);
  - source kinds are `firm_own` and `public`, and `licensed` is refused until a licence exists (ADR-056).

## 21. Future / explicitly deferred
- Per-firm partitions with HNSW.
- Re-embedding on a model change.
- PDF and DOCX.
- Engagement- and client-scoped knowledge, engagement facts and agent-proposed memories.
- Re-ranking and hybrid search.
- Purge on retention.
- A knowledge page.
