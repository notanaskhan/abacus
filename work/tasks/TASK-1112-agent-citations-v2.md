---
id: TASK-1112
title: Persist screener, upload-reviewer and matcher citations as v2 rows through record_citations with the agent's context, inside each handoff unit of work (P-03-T10)
spec: SPEC-322
acceptance_criteria: [AC-1, AC-38]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T10
branch: s7-p03-viewer
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Each verified agent citation becomes one row that resolves to a lit region, and the screening, upload_review and matching suites hold citation_verification 1.0 and every other threshold" (P-03-T10; SPEC-322 AC-1).

## Plan (red zone)
- **Agents (protected):** `agents/v2_citations.py` (new) maps each agent's citations to `evidence.api` claims and anchors:
  - screener: anchor `screening_result:<result>`, `sheet_cell` claims `{evidence_version_id, cell}` with the quote and value;
  - upload reviewer: anchor `upload_review:<review>` with `ref` `F<position>`; a page citation is `document_text {evidence_version_id, page}`, a cell `sheet_cell {evidence_version_id, sheet, cell}`;
  - matcher: anchor `inbox_match:<match>` with `ref` `R<rank>`; the source is the inbox file.
  Each handoff's existing unit of work calls `record_citations(tx, actor=agent, anchor=..., claims=...)` after its rows are inserted, so the v2 rows commit or roll back with the handoff. Every citation is written; v2's verifier decides (an unverified one is stored with its reason; readers show it "Unverified"). The legacy JSON on the handoff rows and the eval metrics are unchanged.
- **Evidence (protected):** `document_text` accepts an inbox file as its source (`inbox_file_id` instead of `evidence_version_id`, exactly one): the matcher cites a file before it is a version. `source_type` `inbox_file`, `match_id` `inbox:<file>#p<page>:<box>`; the actor needs `evidence.read` on the anchor's engagement and the file must be in it. DEC-267.
- **Evals:** not run (`make evals` is never run by agents); the change does not touch prompts, outputs or the graders.
- **Tests (first):** `tests/integration/trust_kit/test_agent_citations_v2.py` (the reviewer's and matcher's quotes become verified rows with a box and `created_by_kind=agent`, run id and initiator; the screener's cell; a fabricated quote is stored unverified; the handoff rolls back with them); unit tests for the claim mapping; the existing agent unit tests pass.
- **Rollback:** revert the commit (rows written meanwhile are dark data, harmless).

## Progress log
- 2026-10-24: plan written.
- 2026-10-24: built. `agents/v2_citations.py` maps the claims; the three handoffs call it inside their unit of work. `sheet_cell` also takes an inbox file (the matcher cites spreadsheet cells too). Tests written first: `tests/integration/trust_kit/test_agent_citations_v2.py` (5), `tests/unit/agents/test_v2_citations.py` (3), and a new screening test that each cited cell is a v2 row. `test_ac14_screen_records_model_called_and_screening_result_created_by_the_agent` pinned the exact audit sequence; it now expects one `citation.created` per cited cell (strengthened, not weakened: still exact, still every event the agent's). The reviewer and matcher have no end-to-end integration suite (their `create_*_run` need a real model route), so their wiring is covered at the `record_agent_citations` level and by the existing unit suites (475 pass). `make evals` not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-267 | Anchors for the three agents, every citation written, and `document_text` on an inbox file | No (ADR-166) |
