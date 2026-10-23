---
id: TASK-1005
title: Citation v2 verifier registry — evidence.register_citable, built-in verifiers document_text (page, bbox, quote hash on the word layer), sheet_cell and request_item, match_id derivation, record_citations, agents' verifiers as adapters (P-03-T06)
spec: SPEC-322
acceptance_criteria: [AC-1, AC-2, AC-3]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T06
branch: s6-citations
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"A fabricated page, bbox, quote or value is stored unverified with a reason, no citation fails only for a missing bbox, and the existing citation unit tests pass unchanged" (P-03-T06; ADR-166 decisions 2 to 4).

## Plan (red zone)
- **Code (evidence, protected):** new package `evidence/citations/`:
  - `matching.py`: the pure checks shared by v2 and the legacy verifiers (normalisation, quote-in-text, cell references, cell and page reasons, amounts, the word-span search and bbox resolution, the layer hash).
  - `registry.py`: `register_citable(kind, verifier, display)`, `CitationClaim`, `Verdict`, `SOURCE_TYPES`; a kind with no verifier is stored unverified `locator_invalid` (ADR-166 §2).
  - `verifiers.py`: `document_text` (version in the anchor's engagement, else `source_not_visible`; page from the word layer, else the extraction's page text; bbox resolved to the quote's word span, `bbox_mismatch` when the box holds no words or not the quote; a quote found on the page but in no word span is verified with no box, AC-3; `quote_sha256` of the normalised words in the resolved box; value among the box's amounts), `sheet_cell` (extraction tables), `request_item` (`requests.api.item_ref`, same engagement); match_id derivation per C4 §3.1; display functions (title and loc rendered by code).
  - `service.py`: `record_citations(tx, anchor=..., claims=..., run_id=...)` verifies every claim, numbers the anchor's stack, writes insert-only `citations` rows (never a quote) and a `citation.created` audit event each; creator kind from the transaction's actor.
  - `evidence/models.py`: `Citation`. `evidence/api.py` exports.
- **Agents (protected):** `agents/document_citations.py` and `agents/citations.py` keep their signatures and outputs and delegate their comparisons to `evidence.api` (the legacy `quote_mismatch` code is kept for the screener's JSON).
- **Migration 0120** (`citation_match_ids`): the 0109 CHECK `^[A-Za-z0-9._:-]{1,80}$` refuses the C4 §3.1 formats (`#`, `,`, `!`, `@`; a document id with a box is about 90 characters). Widened to `^[A-Za-z0-9._:#,!@-]{1,160}$`. Down: the old CHECK. `down_revision` 0119 (T05's; main re-chains).
- **Tests:** `tests/unit/evidence/test_citation_matching.py` (pure checks, match ids); `tests/integration/trust_kit/test_citation_verifiers.py` (AC-1 to AC-3 against stored layers and extractions; the registry; `locator_invalid` for an unregistered kind; rows carry no quote; audit events); the existing `tests/unit/agents/test_agent_citations.py`, `test_upload_reviewer.py` and `tests/unit/scenarios/test_scenario_documents.py` pass unchanged; `test_trust_kit_schema.py` and `test_schema_check_db.py` still pass.
- **Decisions:** DEC-218 (verification rules), DEC-219 (match_id grammar and the widened CHECK).
- **Rollback:** revert the commit and `alembic downgrade 0119` (no rows use the wider grammar until T10 writes agent citations).
- **Deferred:** the masked projection (T13 adds `pii_regions`; the verifier then reads the masked words), agent persistence (T10), display reads (T08).

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built. Matching rules in `evidence/citations/matching.py`; the agents' two verifiers delegate to them and their 115 existing unit tests pass unchanged. A cited value with no quote or box lights the word that prints it. Fixed a bug from 0109 found on the way: `insert_extraction` and `insert_preview` named the dropped one-per-source index in `ON CONFLICT`, so extraction and previews failed for every upload since P-03-T04 (regression test added). JSONB `cited_from_locator` writes SQL NULL (`none_as_null`), since the column's CHECK refuses JSON `null`. 22 unit and 9 integration tests pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-218 | The verification rules for bbox, quote and value on the word layer, and the extraction fallback, were not written down | No (ADR-166) |
| DEC-219 | 0109's match_id CHECK contradicts C4 §3.1 | No (ADR-166, C4) |
