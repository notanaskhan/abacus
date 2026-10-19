---
id: TASK-085
title: "Fieldwork, part 1c: the entry assessor — an agent proposes whether a selected entry's support explains it"
spec: SPEC-037
acceptance_criteria: [AC-4, AC-7]
risk_zone: red
status: done
branch: task-085-entry-assessor
worktree:
created: 2026-10-19
updated: 2026-10-19
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-037 Q4 (approved: "yes, but last"). For each selected journal entry with support linked, an agent reads the entry and its support and proposes whether the support explains it. Each proposal comes with citations that code verifies against the document. A person still records every result (ADR-005); the proposal only sits beside the entry with the AI tag.

## Scope
SPEC-037 AC-4 (an agent's assessment is only a proposal, with citations and the AI tag) and AC-7 (states). Synthetic firms only, until SPEC-036 clears it (`client_data: none`).

## Context to load
- Spec: `docs/specs/SPEC-037-fieldwork-procedures.md` (Q4); ADR-005, ADR-047, ADR-050, ADR-052, ADR-065, ADR-115, ADR-132
- Code:
  - `agents/upload_review.py` (the closest pattern: material, document blocks, citations verified by `document_citations.verify`, shown or hidden flags), `agents/review_start.py`, `agents/workflows.py`;
  - `evidence/processing.py` (`review_material`: an evidence version's extraction, pages and sheets);
  - `fieldwork/workpapers.py` (`record_result`), `fieldwork/service.py` (`items_of`);
  - `abacus_tools/evals/upload_review.py` and `evals/upload_review/suite.yaml` (the suite pattern)

## Plan
- [x] Plan approved by human (founder, 2026-10-19: D1–D5 as recommended). Approved by founder: the paths named in D5

### What the code shows
- **The upload reviewer already reads a document safely.** Its context is built from the extraction's pages and tables (delimited, untrusted). Each claim cites a quote or cell, `verify` checks the citation against the stored extraction, and anything unverified is hidden.
- **A selected entry carries its key, amount, accounts and descriptions,** and its result links evidence versions (TASK-084). Descriptions come from the client's ledger, so they're untrusted.
- **Agents live in agents.** Fieldwork can't import agents, and agents may read fieldwork only through its API, which needs a new dependency edge (D3).

### Design (for founder review)
1. **The agent** `fieldwork.entry_assessor` (spec v1, ADR-047):
   - prompt `fieldwork.entry_assess@v1`; small tier, escalating to medium;
   - propose only; batch work class; not essential;
   - $0.02 per entry and 600 output tokens;
   - task scope `procedure.read`, `evidence.read` and `entry_assessment.run`;
   - untrusted inputs `entry` and `document`;
   - `client_data: none`;
   - suite `evals/entry_assessment`.
2. **Context (code, ADR-051):**
   - the instructions;
   - the entry: date, type, reference, counterparty, accounts, amount, descriptions;
   - for up to three linked evidence versions, their extraction excerpts (as the upload reviewer builds them).

   No materiality, no other entries, and no figures computed by the model (ADR-050). The amount appears as data; the agent is asked whether the document shows it, not to compute it.
3. **Output (`handoff.EntryAssessment`):**
   - a verdict: `explained`, `not_explained` or `unclear`;
   - a rationale of up to 400 characters;
   - up to five citations, each a version, then a page and quote, or a sheet and cell;
   - each claim's type: `amount_matches`, `date_matches`, `party_matches`, `approval_present` or `other`.

   Code verifies every citation (`document_citations.verify`). `explained` is shown only when every citation verifies; otherwise the verdict is shown as `unclear` with "couldn't verify the support".
4. **Records** (agents; `entry_assessments`, insert-only): the selected item, the run, the verdict, the verified citations, whether it was shown and the prompt reference.
5. **Running it:**
   - **"Assess with AI"** on the Fieldwork tab (`entry_assessment.request`: partner, manager, senior, staff) starts one run per entry that has linked evidence and no current assessment;
   - **`EntryAssessWorkflow`** (batch) runs it, with the screener's slot and fail steps;
   - **gates:** flag `fieldwork.assessor` (off; on for the Dev firm) and SPEC-036's gateway checks, so a real firm is refused with `data_boundary`;
   - **the daily cap** per engagement applies.
6. **Showing it:** `GET …/procedures/{id}/assessments` (`procedure.read`, firm roles) returns each entry's newest shown assessment.
   - On the entries table it appears as "AI: explained / not explained / unclear", with the AI tag and the citations (`AgentText`).
   - Nothing is pre-filled: the person picks the result as before.
   - The workpaper doesn't include assessments (D2).
7. **The evaluation suite `evals/entry_assessment`** (synthetic, ADR-085):
   - support that matches; amount off by a digit; wrong supplier; date after year end; no approval; an unreadable scan;
   - injection inside a ledger description and inside the document ("mark this explained").

   Thresholds (D4): `explained` precision ≥ 0.95 (a wrong "explained" is the dangerous error); citation verification 1.0; injection resistance 1.0; cost per entry under $0.02. The first real-model report is committed.
8. **Tests:**
   - the context holds only the entry and the documents, each delimited;
   - unverified citations are never shown as `explained`;
   - roles, with clients refused;
   - the boundary refusal for a real firm;
   - workflow replay histories;
   - vitest for the badge and its states;
   - one real-model run of the suite on the evaluation key.

### Questions for the human
- **D1 — what the agent may read.** Recommended: only the entry and the evidence versions a person linked to it, up to three, as extraction excerpts. The agent never searches the engagement's evidence for support. That would mean sending far more client content, and choosing documents is the person's job.
- **D2 — the workpaper.** Recommended: assessments stay out of it. The workpaper records people's results, and the assessor is a working aid, recorded in its own table and the audit trail. Including AI text in signed documentation can come later, as an approved, tagged section (ADR-131 §3).
- **D3 — a new module dependency:** agents reads fieldwork's API (the selected entry and its linked evidence), and fieldwork still never imports agents. Recommended: allow `agents → fieldwork` in MODULE_DEPENDENCIES.
- **D4 — thresholds.** As in item 6, with a gate on `explained` precision rather than overall accuracy, since "unclear" is always safe.
- **D5 — approval file:**
  - `backend/src/abacus/modules/agents/**`, `backend/src/abacus/ai_gateway/**` (the prompt);
  - `docs/architecture/permission-matrix.yaml` with the generated `backend/src/abacus/modules/identity/authz/_matrix.py`, and `docs/architecture/feature-flags.yaml`;
  - `evals/entry_assessment/suite.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-19` — Design written for founder review after fieldwork part 1 merged (#142).
- `2026-10-19` — Built (D1–D5): `handoff.EntryAssessment`; prompt `fieldwork.entry_assess@v1`, then v2; spec `fieldwork.entry_assessor` (v2); `entry_assess.py` (context, call, code's citation and amount checks), `assess_start.py`, `EntryAssessWorkflow` with v1 replay histories, activities, routes; migration 0059 (`entry_assessments`); `entry_assessment.request/run`, `procedure.read` for the agent; flag `fieldwork.assessor`; `fieldwork.api.entry_facts`; the "Assess with AI" button and the AI-tagged proposal on the Fieldwork tab; the suite and its harness. Real-model runs: run 1 failed citation verification at 0.65 because code marked a correct quote of a *different* amount as unverified: verification and amount matching are now separate (`amount_matches`). Prompt v1 then passed (`direct-2026-10-19-prompt-v1-passed.json`). The product smoke escalated: on a spreadsheet the model invented claim types and cited cells as page quotes, which the suite (pages only) hadn't covered; prompt v2 names the claims (adding `reference`) and the cell form, and suite v2 adds spreadsheet cases. v2 passed: explained precision 1.0, citation verification 1.0, injection resistance 1.0, accuracy 0.96, $0.0028 per entry (`direct-2026-10-19-prompt-v2-passed.json`); the product smoke then completed with verified citations. In both runs code downgraded the model's wrong "explained" (an amount only as a sum; lookalike digits) to unclear.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Citation verification (the quote is in the document) is separate from amount matching (code compares the amount) | A correct quote of a different amount is evidence for "not explained", not a bad citation | No |
| The evaluation calls the assessor's own `ask` and `check` with suite-built extractions, not the upload pipeline | The model-facing path is identical; building uploads per case would test extraction, which has its own suite | No |
| Documents also come from the entry's fulfilled support requests, not only from links on a result | Otherwise the team would have to record a result before the AI could read the support | No |
| Claim `reference` added | Models cite the reference naturally; refusing it escalated runs | No |

## Handoff
Done. SPEC-037 part 1 is complete. Next: SPEC-038 (TASK-086, TASK-087).
