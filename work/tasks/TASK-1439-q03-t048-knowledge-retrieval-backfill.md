---
id: TASK-1439
title: Back-fill TASK-024, knowledge retrieval on pgvector, from SPEC-009 (Q-03-T048)
spec: SPEC-009
acceptance_criteria: [AC-1, AC-3, AC-4, AC-5, AC-7, AC-8, AC-9]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T048
branch: s11-trust-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s11-trust-tests (S11 lane 7; a clean session following .claude/skills/ac-test-author/SKILL.md, from the spec, contracts and ADRs only)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Retrieval never returns another tenant's chunk and walled engagements' chunks are excluded."

## Plan (red zone)
- **File:** `backend/tests/integration/backfill/test_q03t048_knowledge_retrieval.py`, over HTTP;
  the embedding workflow's activity `knowledge.embed_batch` run until done; the synthetic embedder.
- Walls: DEC-580 (knowledge is firm-wide, SPEC-009 §9). No production change. Rollback: delete.

## Results (19 tests, all pass)
- AC-1 pending, chunked, fingerprinted, audited, then ready; only admin/leader add. AC-3 unknown
  source kind or media type 422, duplicate 409, over 1 MB refused; nothing stored. AC-4 withdraw
  leaves search at once, audited. AC-5 ingestion and query embeddings metered (`prompt_id embed`).
  AC-7 chunks on another model leave search and the document reads `stale`. AC-8 provenance
  fields, score order, pending never returned, k 1–20, client refused. AC-9 two firms with the same
  text never see each other's chunk (search, read, list, withdraw); a person in both firms gets the
  firm they act for; forced RLS and no HNSW/IVFFlat index. Walls: no engagement/client/entity
  column; a walled member's results equal an unwalled colleague's.

## Spec drift followed
- AC-3 over 1 MB: the API's JSON body cap answers 413 before the knowledge limit.
- AC-7: the model change is simulated on the stored chunks (an unregistered configured model makes
  the query embedding unavailable, 503, rather than exercising the rule).

## Not covered
- AC-2 chunking determinism and AC-10 `knowledge_context` are pure functions with unit tests;
  AC-6 resume after an outage needs a failing provider.

## Progress log
- 2026-10-27: suite written; targeted pass 17 passed, 2 test-setup fixes (drift above); re-run 2 passed.
