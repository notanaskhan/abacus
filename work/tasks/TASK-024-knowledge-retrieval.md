---
id: TASK-024
title: Knowledge retrieval infrastructure (pgvector), without content
spec: SPEC-009
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
risk_zone: red
status: awaiting-plan-approval
branch: task-024-knowledge-retrieval
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-009 (approved, Q1–Q5): knowledge documents and chunks, deterministic chunking, embedding through a new `ai_gateway.embed` (metered, budgeted, admitted), a batch-class embedding workflow, and firm-scoped exact similarity search.

## Scope
All of SPEC-009. Excluded: content, PDF and DOCX, ANN indexes, re-embedding, and any UI.

## Context to load
- Spec: `docs/specs/SPEC-009-knowledge-retrieval.md`
- ADRs: ADR-053, ADR-056, ADR-019, ADR-069, ADR-072, ADR-052
- Code: `ai_gateway/` (`_call`, `_admitted`, `_record_usage`, `budgets`), `modules/agents/` (`screenings.py` for the outbox subscription and workflow pattern), `kernel/dispatch`

## Plan
- [ ] Plan approved by human

### Design (for founder review)
1. **`ai_gateway.embed(EmbedCall) -> EmbedResult`** (`ai_gateway/embeddings.py`):
   - **`EmbedCall`:** `purpose`, `texts` (1 to 64, each at most 2,000 characters), `attribution`, `work_class`, `essential` and `budget_usd`.
   - **Order of checks:** the per-call budget on an estimate (characters ÷ 4 × price), then `check_budget` (SPEC-007), then `_admitted` on the embedding model (SPEC-003 capacity; `provider_limits` gains `fake-embed`), then the provider.
   - **The usage record** (AC-5) reuses `usage_records`, with no schema change:
     - `prompt_id` `embed`, `prompt_version` `1`;
     - `tier` `small` (embeddings count as the cheap tier);
     - `output_tokens` 0;
     - outcome `ok`, `budget_refused` or `provider_error`;
     - `inputs_hash` is the SHA-256 of the texts.
   - **Spans:** identifiers only, as for `call`.
2. **`EmbeddingProvider` protocol** (`embed(model, texts) -> EmbeddingResponse(vectors, input_tokens)`):
   - `FakeEmbedder` (synthetic environments only) is deterministic: hashed word features over 1,024 dimensions, L2-normalised. Similar texts score closer, so ranking tests mean something.
   - Settings: `embedding_model` (`fake-embed`), `embedding_dimensions` (1,024) and the price per million tokens.
   - The real provider arrives with ADR-073 (Q2).
3. **Data** (migration 0020, owned by `agents`, Q5):
   - `CREATE EXTENSION IF NOT EXISTS vector`;
   - **`knowledge_documents`:** as in SPEC-009 §7, with a partial unique index on (`tenant_id`, `fingerprint`) where status isn't `withdrawn`;
   - **`knowledge_chunks`:** primary key (`tenant_id`, `document_id`, `position`), `embedding vector(1024)`, and a btree on (`tenant_id`, `document_id`); no ANN index (Q1);
   - column grants per §7, plus the schema-check maps.
4. **Python `pgvector`** (on the allowlist) for the SQLAlchemy `Vector` type. It is added to `pyproject.toml` and the lock file.
5. **Chunking** (`agents/knowledge_chunks.py`, pure):
   - split on Markdown headings (`#` to `######`), which keep a heading path;
   - then split on blank-line paragraphs, packing them up to 1,200 characters;
   - a longer paragraph is split at the last whitespace before the limit, with a 150-character overlap;
   - plain text has no headings;
   - deterministic, with golden tests later.
6. **Ingestion** (`agents/knowledge.py`):
   - **`add_document(ctx, NewDocument)`:**
     1. `authorise("knowledge.manage")` on the firm;
     2. validate: 1 MB, UTF-8 (a JSON string is already decoded; the byte length is checked), `text/plain` or `text/markdown`, `firm_own` or `public`, at most 2,000 chunks per document and 50,000 per firm;
     3. in one unit of work, the document (`pending`), its chunks, the audit event `knowledge_document.added`, and the outbox event `knowledge_document.added`.

     Errors are `KnowledgeInvalid` subclasses (422, fixed codes); a duplicate is 409 `knowledge_duplicate`.
   - **`withdraw_document(ctx, id)`:** `pending` or `ready` → `withdrawn`, audited.
7. **`KnowledgeEmbeddingWorkflow`** (batch class, registered in `WORKFLOWS`):
   - started by the outbox subscription for `knowledge_document.added`, with workflow ID `knowledge-embed:{tenant}:{document}`;
   - activity `embed_next_batch(tenant_id, document_id)`:
     1. stop if the document isn't `pending`;
     2. take up to 64 chunks with no vector;
     3. call `embed` (batch, deferrable), attributed to the firm with agent ID `knowledge.embedder`;
     4. store the vectors in one unit of work with `knowledge_chunk.embedded` audited (document target, count);
     5. return how many remain.
   - At 0, the document becomes `ready` (audited).
   - `BudgetExceeded`, `BudgetExhausted` or a refused call: the document becomes `failed` with a fixed code (audited).
   - Provider errors are retried by Temporal (resume is natural: only chunks without vectors are taken).
8. **Search** (`search_knowledge(ctx, query, k)`):
   - `authorise("knowledge.read")` on the firm, with `k` capped at 20 and the query at 1,000 characters;
   - `embed` the query (interactive, essential=False);
   - one SQL query: `… WHERE c.tenant_id = :tenant AND d.status = 'ready' AND c.embedding_model = :model ORDER BY c.embedding <=> :q, c.document_id, c.position LIMIT :k`, with score = 1 − distance;
   - `knowledge_context(hits)` returns `ContextBuilder` sections labelled untrusted and classified internal (AC-10).

   Routes are in the `agents` module (`knowledge_router`), per SPEC-009 §8. Status `stale` (AC-7) is computed on read.
9. **Matrix:** `knowledge.manage` (firm_admin, practice_leader, `mfa_recent`) and `knowledge.read` (firm_admin, practice_leader, quality_partner, engagement_partner, manager, senior, staff, reviewer), then the codegen. Engagement roles meet the firm-level-read limit noted in TASK-023 (see D3).

**Protected paths (approval file):**
- `backend/src/abacus/ai_gateway/**` and `backend/src/abacus/modules/{agents,identity}/**`;
- `backend/migrations/**` and `backend/src/abacus/kernel/config.py`;
- `backend/pyproject.toml` and `backend/uv.lock`;
- `docs/architecture/permission-matrix.yaml`;
- `backend/src/abacus_tools/quality/{schema_check,banned_patterns}.py`, `backend/tests/unit/**` (pins);
- `backend/src/abacus/api/**` and `backend/src/abacus/worker/**`.

### Questions for approval
- **D1. Embedding usage goes in the existing `usage_records` as `prompt_id` `embed` with tier `small`, with no schema change?** *Recommendation: yes.* Metering and budgets then work unchanged.
- **D2. Add the allowlisted Python `pgvector` package for the `Vector` column type?** *Recommendation: yes.* It's already approved in the dependency allowlist.
- **D3. `knowledge.read` is checked at firm level, so engagement-only users (partners, managers, seniors and staff without a firm role) are refused until firm-level reads can honour engagement roles (the TASK-023 limitation)?** *Recommendation: accept for v1 and fix both together later.* Alternative: let `authorise` treat "has any engagement role in the firm" as holding engagement roles for firm-level reads. That is a small authz change, but it touches identity, a protected and red area.
- **D4. Write the approval file for the protected paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-07` — SPEC-009 approved and merged (#42). Design written for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Questions for the human
- Design questions D1–D4 (above).

## Handoff
