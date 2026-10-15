---
id: TASK-072
title: "Drafted guidance, part 1: the guidance drafter, its code checks, its evaluation suite and first real-model report"
spec: SPEC-035
acceptance_criteria: [AC-2, AC-3, AC-7]
risk_zone: red
status: done
branch: task-072-guidance-drafter
worktree:
created: 2026-10-15
updated: 2026-10-15
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-035 §7, TASK-072: build the guidance drafter and measure it on synthetic request lists. It doesn't run in the product yet; that's TASK-073.

## Scope
SPEC-035 AC-2, AC-3, AC-7.

## Context to load
- Spec: `docs/specs/SPEC-035-drafted-guidance.md`; ADR-047, ADR-051, ADR-052, ADR-081, ADR-111, ADR-112
- Code (copy the matcher, TASK-065):
  - `agents/inbox_match.py`, `agents/handoff.py`, `agents/specs/`;
  - `ai_gateway/prompts/`;
  - `abacus_tools/evals/matching.py`, `abacus_tools/evals/graders.py` (the judge and its calibration rule);
  - `requests/guidance.py` (the kind defaults), `abacus_tools/synthetic/requests.py`

## Plan
- [x] Plan approved by human (founder, 2026-10-15: D1–D3 as recommended). Approved by founder: the paths named in D3

### What the code shows
- **The matcher is the full pattern:** spec, prompt, output schema, context builder with an untrusted field, code checks after the call, insert-only records, an evaluation runner on a throwaway stack's synthetic firm, and a report.
- **The judge must be calibrated before it can gate.** A model judge needs a record in `evals/judges/` showing at least 90% agreement with human labels for its prompt, model and tier (`graders.judge_record`). There is no record yet for a rubric about guidance.
- **Synthetic request lists exist** (`abacus_tools/synthetic/requests.py`), as do the four kind defaults the founder approved (SPEC-031 D3), which are good examples of the voice wanted.

### Design (for founder review)
1. **Agent spec** `requests.guidance_drafter` v1:
   - prompt `requests.guidance_draft@v1`; small tier; `autonomy: propose`;
   - task scope `request_item.read` and `guidance_draft.run`;
   - limits: 400 output tokens, $0.005, one step, 30 seconds;
   - untrusted input: the item; suite `evals/guidance_drafting`; batch work class; essential `false`.
2. **Output** `GuidanceDraft`:
   - `why` (1–300 characters) and `good_looks_like` (1–600);
   - optional `effort` (small, medium, large) and `blocks_fieldwork` (bool), each with a reason of up to 160 characters for the firm.
3. **Context** (`agents/guidance_draft.py`, code only):
   - the instructions, with the four approved kind defaults as examples of the voice;
   - the year end;
   - the item (description, area, document kind, tier), delimited as untrusted (SPEC-035 Q1);
   - up to three of the firm's own guidance texts from other items, also delimited (Q4).
4. **Code checks** (pure, `agents/guidance_checks.py`). A failing draft is recorded with its reason codes and never shown. The checks:
   - length bounds;
   - no URL, email address or phone number;
   - no amount (currency or a number with thousands separators);
   - no date other than "year end" wording, and no year that isn't the engagement's;
   - no first-person model talk ("as an AI", "I");
   - no instruction to the auditor or reviewer;
   - not a copy of the description (more than 80% word overlap);
   - no capitalised names that aren't in the input or a short allow-list of document words (to catch invented parties).
5. **Data** (migration 0052, agents, insert-only):
   - `guidance_drafts`: id, engagement (nullable for templates), request item or template item (exactly one), agent run, the draft fields, check outcome and reasons, created_at;
   - `guidance_draft_decisions` follows in TASK-073 with the review screens.
6. **Run functions:** `create_draft_run(tenant, target, event, person)` and `draft(agent, target)`, with the same guards as the matcher (an active person, a real route, the daily cap; `data_boundary` for non-synthetic firms). No trigger or screen yet.
7. **Evaluation suite** `evals/guidance_drafting` and its runner:
   - about 40 synthetic items across the audit areas (bank, receivables, payables, inventory, fixed assets, debt, equity, revenue, payroll, leases, legal, insurance, governance, tax), with plain and terse descriptions;
   - five injection cases (instructions inside a description, an addressed note, Unicode tricks);
   - three cases with fact-bait (a description naming an amount or a person) to check none is copied into the client text beyond what's given.
   - **Code-graded metrics (gating):** `form_pass` (shown drafts passing every check), `no_invented_facts`, `injection_resistance`, `cost_per_item`.
   - **The rubric judge** (`eval.guidance_judge@v1`) scores 1–5 on four points: says why, describes a complete document, plain English, no unexplained jargon. See D1.
8. **First real-model report:** on the synthetic tenant, with the small tier at temperature 0, saved to `docs/operations/guidance-drafting/`. If it misses a gating threshold, I stop and bring you the failing cases.
9. **Tests:**
   - each check refuses its case and lets a good draft through;
   - output schema bounds;
   - the item is the only untrusted field besides the examples;
   - the boundary refusal;
   - insert-only grants;
   - the suite validates and grades with a fake model.

### Questions for the human
- **D1 — the rubric judge needs human labels before it can gate.** The platform only lets a model judge gate once it agrees with human labels at least 90% of the time. Recommended: in this task the judge's scores are reported but don't gate. The gate is the code-graded metrics (form, no invented facts, injection, cost). I'd then prepare 30 synthetic drafts for you to score 1–5 on the same rubric (about 20 minutes). Your labels become the judge's calibration record, and the rubric threshold (average at least 4, none below 3) gates from then on. Alternative: wait for the labels before measuring at all.
- **D2 — invented names check.** Recommended: flag any capitalised word sequence that's neither in the input, nor at the start of a sentence, nor on a short allow-list of document words (Statement, Trial Balance, Form W-2 and so on). It's strict, so a few good drafts may be refused, and the report shows how many.
- **D3 — approval file:**
  - `backend/src/abacus/modules/agents/**`, `backend/src/abacus/ai_gateway/**`;
  - `docs/architecture/permission-matrix.yaml`, `backend/src/abacus/modules/identity/authz/_matrix.py` (`guidance_draft.run`);
  - `evals/guidance_drafting/suite.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] The suite runs against the real model on the synthetic tenant, and the report is committed
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-15` — Design written for founder review after SPEC-035 merged (#126).
- `2026-10-15` — Built (D1–D3): spec, prompt `requests.guidance_draft@v1`, `GuidanceDraft`, `guidance_draft.py`, `guidance_checks.py`, migration 0052, `guidance_draft.run`, the suite (45 cases, 50 attempts) and its runner with an informational rubric judge. Unit tests and gates pass.
- `2026-10-15` — Real-model runs (Haiku 4.5, temperature 0, synthetic tenant). Run 1 failed: two drafts wrote "as of 31 December 2025" (the check allowed the engagement's year and missed day-month dates), and the harness checked containment against the upload reviewer's field name. Fixed: dates and any year are refused (guidance is copied on roll-forward), the prompt says so, the harness checks the `item` block. Run 2 showed two false positives in my code (containment with two untrusted blocks; "to the auditors," read as an instruction); fixed. Run 3 **passed**: form 1.0, no invented facts 1.0, injection resistance 1.0 (no injected instruction followed in any run), $0.0019 per item. Rubric (informational): average 4.36, three cases at 2 (lease schedule and representation letter: jargon; "JE listing": the why didn't say what the audit uses it for). Report: `docs/operations/guidance-drafting/direct-2026-10-15-prompt-v1-passed.json`. Labelling sheet for D1: `docs/operations/guidance-drafting/labels-to-score.csv` (30 drafts).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Request items only; template drafting moves to TASK-073 | `agent_runs.engagement_id` is required, so a template item (no engagement) can't have a run without a schema change | No |
| Any year or specific date is refused, the engagement's own included | Guidance is copied on roll-forward, where a date would be wrong | No |

## Handoff
Done. Waiting on the founder's scores in `labels-to-score.csv` to write the judge's calibration record (D1). Next: TASK-073 (product, review, client display, templates).
