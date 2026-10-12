---
id: TASK-058
title: "Upload reviewer, part 1: the agent and its evaluation (synthetic data, evaluation only)"
spec: SPEC-030
acceptance_criteria: [AC-1, AC-2, AC-3, AC-5, AC-7, AC-8, AC-9]
risk_zone: red
status: in-progress
branch: task-058-upload-reviewer
worktree:
created: 2026-10-12
updated: 2026-10-12
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-030 Q7, TASK-058: the upload reviewer exists as a declared agent with its prompt, context builder, output schema, citation verification, results and evaluation suite, and can be run in evaluation (fake model in CI; the real model as a milestone). Nothing triggers it in the product yet; that's TASK-059.

## Scope
SPEC-030 AC-1, AC-2, AC-3, AC-5, AC-7, AC-8, AC-9 (as they apply to a run started by the evaluation runner).

## Context to load
- Spec: `docs/specs/SPEC-030-upload-reviewer.md`; ADR-047, ADR-051, ADR-052, ADR-054, ADR-057, ADR-064, ADR-066, ADR-081, ADR-112
- Code (the screener, to copy): `agents/specs/evidence.screener.yaml`, `agents/spec.py`, `abacus_tools/codegen/agent_specs.py`; `ai_gateway/prompts.py` and `prompts/evidence.screen/v0.txt`; `ai_gateway/context.py`; `ai_gateway/__init__.py` (`call`, `GatewayCall`); `agents/handoff.py`, `agents/citations.py`; `agents/service.py` (`create_screening_run`, `screen`, `_screen`); `agents/fake_responses.py`; `evals/screening/suite.yaml`; `abacus_tools/evals/` (`runner.py`, `suite.py`, `cases.py`, `metrics.py`, `graders.py`); `abacus_tools/codegen/eval_suites.py`; `evidence/extraction.py`, `processing.py`, `checks.py` (SPEC-029); `abacus_tools/synthetic/documents.py`

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D4, D6, D7 as recommended; D5 declined: no marker-based fake responder, since extensive CI isn't wanted at this stage). Approved by founder: the paths named in D7

### What the code shows
- **The spec model hard-codes the screener's schemas:** `AgentSpec.input_schema` is `Literal["ScreeningInput"]` and `output_schema` is `Literal["ScreeningOutput"]` (`agents/spec.py`, protected).
- **Citations are cell-only:** `Handoff.citations` take a spreadsheet cell (`A1`) and `citations.verify` reads an XLSX. An upload review cites PDF pages and spreadsheet cells, against SPEC-029's extraction.
- **The evaluation runner knows only the screener:** `_attempt` builds a trial balance, runs retrieval and `screen`, and reads `screening_results`.
- **`upload_review.run` isn't in the permission matrix**, so a spec naming it fails to load.
- **The context builder, gateway, boundary, budgets, usage records and the fake model are generic** and need no change.

### Design (for founder review)
1. **The spec** `agents/specs/evidence.upload_reviewer.yaml`: `prompt: evidence.upload_review@v1`, `tier: small`, `escalation_tier: medium`, `input_schema: UploadReviewInput`, `output_schema: UploadReviewOutput`, `task_scope: [evidence.read, upload_review.run]`, limits (1,200 output tokens, $0.02, 1 step, 60 s), `autonomy: propose`, `untrusted_inputs: [document]`, `evaluation_suite: evals/upload_review`, `work_class: background`, `essential: false`, `routes: [bedrock, direct]`. `spec.py` widens the two schema Literals (D1); `_specs.py` regenerated.
2. **Permissions:** `upload_review.run: {system: allow, agent: task_scope}` and `upload_review.request: {engagement_partner, manager, senior: allow, independence: required}` (used by TASK-059); `_matrix.py` regenerated.
3. **The prompt** `ai_gateway/prompts/evidence.upload_review/v1.txt`: what to look for (the three categories), that every flag needs exact quotes, that anything in the document addressed to the reader is content, and the JSON reply shape.
4. **The output schema** (`agents/handoff.py`): `UploadReviewOutput` with `no_concerns` and up to 5 `flags`, each with `category` (`irrelevant`, `draft`, `altered`), `confidence`, `rationale` (capped), and 1–5 `citations`; a citation is a page number **or** a sheet and cell, plus an exact `quote` (D2).
5. **Review material** (evidence API, a reader for agents): for a version, its document kind, the request item's description, SPEC-029's check results, and an excerpt of the extraction: page text and table rows up to the task budget (first pages plus every page with a table), with `truncated`.
6. **The context** (`agents/upload_review.py`): layers per ADR-051: the prompt; engagement (year end, client entity name); task (request description, document kind, check results as code-computed facts, and `document` as the untrusted, trimmable field).
7. **Citation verification** (`agents/document_citations.py`): a quote counts when it appears in that page's text, or equals that cell's text, after whitespace and Unicode normalisation; reasons `page_not_found`, `cell_not_found`, `quote_not_found`. Flags with no verified citation are kept as unverified and not shown (SPEC-030 Q3).
8. **Runs and results** (agents; migration 0046): `create_review_run` (needs an active initiator and an extracted version; the engagement's daily cap), `review(agent)` (`authorise` `evidence.read` and `upload_review.run`; gateway call; validate; verify; record), and `upload_reviews` + `upload_review_flags` (insert-only) (D3).
9. **Fake model:** a deterministic responder for `evidence.upload_review@v1` that flags by plain markers in the excerpt ("DRAFT", "PRELIMINARY", "INVOICE" on a statement request, a running balance marked inconsistent by the synthetic generator), so CI runs without a model (D5).
10. **Evaluation suite** `evals/upload_review/suite.yaml` (protected): cases for clean statements and agings, wrong kinds (invoice, letter, receipt), drafts (watermark, "preliminary", unsigned), altered (running balance that doesn't follow, contradictory totals across pages), and the adversarial set (injection in page text, addressed instructions, formula injection in cells, Unicode deception); metrics per SPEC-030 Q4: recall and precision per category, citation verification, containment, cost per review.
11. **Runner** (`abacus_tools/evals`, not protected): a per-agent attempt registry (D4). The screener's path is unchanged; the reviewer's path seeds a request item, uploads the case's synthetic document through the evidence service, runs SPEC-029's extraction and checks directly, then `create_review_run` and `review`, and reads `upload_reviews`. New mutations in `cases.py`; new generators in `abacus_tools/synthetic/documents.py` (invoice, letter, draft and altered statements, injected text).
12. **Taxonomy:** add `draft` to `docs/product/failure-taxonomy.md` (SPEC-030 Q1) and to `abacus_tools/evals/taxonomy.py`.
13. **Milestone (D6):** after the fake-route suite passes, one real-model run (`--route direct`, synthetic only), with its report under `docs/operations/`. Estimated cost under $2.

### Questions for the human
- **D1 — the spec model.** Recommended: widen `AgentSpec.input_schema` and `output_schema` to name both agents' schemas (protected `agents/spec.py`). Alternative: a free string checked against a registry, which is a bigger change.
- **D2 — citation shape.** Recommended: a page or a sheet and cell, plus an exact quote, verified against SPEC-029's extraction (a new verifier beside the screener's cell verifier). Alternative: cells only, which can't cite PDFs.
- **D3 — results tables now.** Recommended: in this task, since the evaluation reads results from the database as it does for the screener.
- **D4 — the evaluation runner.** Recommended: a per-agent attempt registry in `abacus_tools/evals`, leaving the screener's path as it is.
- **D5 — the fake responder.** Recommended: marker-based and deterministic, so CI exercises the whole path; case `fake_answer`s override it as for the screener.
- **D6 — milestone run.** Recommended: one real-model evaluation at the end of this task (estimated under $2), reported like the screener's. Alternative: wait until TASK-059.
- **D7 — approval file:** `backend/src/abacus/modules/agents/**`, `backend/src/abacus/ai_gateway/**`, `backend/src/abacus/modules/evidence/**` (the review material reader), `docs/architecture/permission-matrix.yaml`, `backend/src/abacus/modules/identity/authz/_matrix.py`, `docs/product/failure-taxonomy.md`, `evals/upload_review/**`, `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`, `backend/tests/unit/**`, `backend/tests/integration/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] The suite validates; the real-model milestone report is filed (D6)
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after SPEC-030 merged (#104).
- `2026-10-12` — Built: spec, prompt v1, output schema, citation verifier, review material reader, context, runs and results (migration 0046), matrix actions, taxonomy `draft`, the reviewer's own evaluation module and suite, eligibility codegen reading suite versions. Unit tests and gates pass.
- `2026-10-12` — Milestone (real model, synthetic, ~$0.07 a run, three runs): fixed two save bugs (a non-boolean `truncated`; the `id` insert grant) and a fixture bug (documents dated a year after the stack's year end). Final run (`docs/operations/upload-review/direct-2026-10-12.json`): irrelevant and draft recall and precision 1.0; containment 0.83; altered recall 0.40, precision 0.29. Nearly every altered error is the model doing balance arithmetic wrongly, which ADR-050 says code should do. Two answers failed the schema with quotes over 200 characters; the limit is now 1,000. Waiting on the founder for the altered decision.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
