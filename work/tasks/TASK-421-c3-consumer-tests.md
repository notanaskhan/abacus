---
id: TASK-421
title: C3 consumer contract tests for stubs 1 and 2 (SHL-10 a-g, SHL-11 a-h, SHL-12 a-h); schema v1 freeze scheduled (P-04-T09)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: P-04
plan_key: P-04-T09
branch: p04-t09-c3-consumer-tests
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"The consumer tests run green in the provider CI and fail if a field the artboards need is removed, and the register marks C3 schema v1 frozen by Fri Dec 11, 2026 (S3)."

## Plan (amber)
- **Files.**
  - `backend/tests/contracts/review_grammar/` (new): the `_c3.py` helpers and four test files (stubs, SHL-10, SHL-11, SHL-12).
  - `apps/web/src/fixtures/contracts/review-grammar.test.ts` (new): typed fixture frames per artboard.
  - Docs: `docs/contracts/README.md` (the C3 row and a dated freeze note) and `docs/contracts/review-grammar.md` (§9 and §10).
- **Migrations, flags and the matrix.** None. The tests read migrations 0093 to 0095 as text.
- **Tests.** Pytest against the stubs: route actions, 404 off and 501 on through every handler, the matrix, status enums, migration CHECK lists, and the per-artboard fields with their classification tags. Every §8 example in `review-grammar.md` is validated as written, and the figures foot as `Decimal`. Vitest frames per artboard are typed against `@abacus/api-client` and checked against `openapi.json`, with figures footed in bigint.
- **Freeze.** Today is 2026-10-22, so C3 is not marked frozen. The register gets a dated note that the freeze is scheduled for Fri Dec 11, 2026, with these suites as the gate.
- **Defects.** A real contract defect is not weakened. It gets an `xfail(strict=True)` with an issue reference, and it is recorded here.
- **Rollback.** Revert the commit.

## What changed
- **Pytest, `backend/tests/contracts/review_grammar/`** (348 passed, 1 strict xfail):
  - `test_c3_stubs.py` (stubs 1 and 2 as a whole):
    - the 25 routes declare their one matrix action, with 404 and 501 in their responses;
    - each handler, called directly, answers 404 with `review.grammar_api` off and 501 with it on;
    - the bulk sign-off requires `Idempotency-Key`;
    - the 21 human-only actions deny `agent` and `system`, with no non-firm grant, and the 13 rows that §5 names deny `system` explicitly;
    - the reads go to firm roles only, and the agent holds only `proposal.create` and `suggestion.create` (`task_scope`);
    - the status enums equal the registry's stored codes, and `sign_off_slot` is derived (`stale` is a computed boolean);
    - the CHECK lists in 0093 to 0095 equal the wire enums and literals, and the human-only constraints exist;
    - every field of every C3 model is classified;
    - the operation ids and the C3 component names (`AgentProposalOut`, `AgentSuggestionOut`, `ReviewNoteDetailOut`, `CardDecisionOut`, `CardDecideIn`) are unique (#284).
  - `test_c3_shl12_sign_offs.py` (SHL-12 a to h, 64 tests):
    - the field table per artboard, with tags (the sealed note bodies are Restricted, and list rows carry none);
    - the §8 eligibility, sign, 201 and notes-list examples conform exactly;
    - 14 of 14 cited; the L1 is run #4127 adopted by MD; "✓ MD ✓ HL";
    - the abbreviated hash is refused on the wire and the full digest is accepted;
    - bulk is 3 signed + 3 excluded = 6; 16,812,400 + 48,600 = 16,861,000; EQR sees L5 only; final approval has 11 open issues.
  - `test_c3_shl11_decision_cards.py` (SHL-11 a to h, 56 tests):
    - the field table, with the rationale Restricted in `CardDecideIn`, `CardDecisionOut` and `DecisionCardOut.decision`;
    - the §8 card, decide and decision examples conform;
    - the options foot as `Decimal`: round(rate × 16,812,400, 100), PM 75%, CT 5%. That gives 168,100 / 126,075 / 8,405 and 252,200 / 189,150 / 12,610, and the label and "v2: …" line agree;
    - the v3 inline example: 1.5% × 16,861,000 → 252,900, a difference of $700, no change;
    - the viewer outside the role gets no decide; the list row carries nothing Restricted;
    - an xfail for #285.
  - `test_c3_shl10_proposals.py` (SHL-10 a to g, 72 tests):
    - the field table, with reasoning, rows, totals, policy, decision, before and after, the policy note and edit values Restricted;
    - the K-1 example conforms, and the net change to Form 1040 total income over the Sch E lines is 0, a tie (the QBI line is excluded);
    - an edit needs a citation note; the line 2a suggestion adopts 1,550;
    - the uncited row 5 (18,240);
    - AJE-05 = 12,600.00 + 1,480.00 + 820.00 = 14,900.00, over $10,000, routed to Priya Raman;
    - the 10 s Undo window; the four reject reasons; the set link (40 results, 1 exception).
- **Vitest, `apps/web/src/fixtures/contracts/review-grammar.test.ts`** (24 tests):
  - one typed frame per artboard: SHL-12 a, b, c, d, e (ladder), f (bulk), g, h; SHL-11 a, b, c, d, e (list), f, g, h; SHL-10 a, b (approve with edits, suggestion adopt), c, d, e′, f, g;
  - each frame is checked by `validateResponse` and `validateSchema`;
  - the classification tags are read from `openapi.json`, and the same figures foot in bigint.
- **Docs.**
  - The C3 row in `docs/contracts/README.md`, and a dated note: freeze scheduled for Fri Dec 11, 2026, these suites as the gate, the finding to clear first (#285), and the `--freeze review_grammar v1` step.
  - `review-grammar.md` §9 lists the suites, and §10 records the date.

## Findings (contract defects)
1. **#284, generated names collided. Fixed on main by TASK-422 before this merged.**
   - `GET /v1/proposals/{ref}` has operationId `proposal`, which `POST /v1/engagements/proposal` already holds. The client calls it `proposal2`, and FastAPI warns about the duplicate.
   - `ProposalOut`, `SuggestionOut`, `ReviewNoteOut`, `DecisionOut` and `DecideIn` collide with older models, so the C3 types are named by module path (`AbacusModulesAgentsContractProposalOut`).
   - Effect on main: `apps/web` `tsc --noEmit` already fails in `src/legacy/Review.tsx` (`ProposalOut`, lost in P-04-T08), `src/legacy/ReviewableNotes.tsx` and `src/legacy/spec313review.test.tsx` (`ReviewNoteOut`, lost in P-04-T07).
   - These were strict xfails. TASK-422 (b66c637) landed the renames while this task was in flight, and the rebase turned them into passing guards: `test_c3_operation_ids_are_unique_in_the_document` and `test_c3_models_have_their_own_component_names`. The issue is closed with a pointer to TASK-422.
2. **#285, decision-card classification. Open, strict xfail.**
   - These fields are Confidential: `DecisionContextOut.value` (client net assets), `DecisionOptionOut.figures` and `DecisionCardVersionOut.figures` (client figures; §754 step-up as return information in SHL-11 g), and `DecisionRecommendationOut.reasons` (agent reasoning).
   - ADR-031 and P-04's §7216 note make them Restricted, as the proposal contract already tags the same data.
   - Test: `test_shl11g_client_figures_and_agent_reasons_are_restricted`.

#285 should be fixed by the provider before the Dec 11 freeze. It does not change the wire shape the artboards need.

## Notes
- The level rows (`sign_off.prepare` … `sign_off.eqr`) and `review_note.raise`, `.respond` and `.clear` have no explicit `system` cell. That is a deny by absence, which authorise and visible treat as deny, so the tests assert the effective deny. P-04-T15's generated I-AGENT-NEVER tests may make it explicit.
- The TS frames import the TASK-422 names (`AgentProposalOut`, `CardDecideIn` and the rest).

## Progress log
- 2026-10-22: built per the S3 batch rules. Only the new files were run.
  - pytest `tests/contracts/review_grammar`: 339 passed, 7 xfailed (strict).
  - ruff format and check and pyright on them: clean.
  - vitest on the new file: 24 passed. eslint and prettier: clean. tsc: no error in the new file. The 16 existing `apps/web` tsc errors on main include the #284 effect above.
  - banned_patterns and validate_docs: clean (exit 0).
  - Issues #284 and #285 opened for the two findings.
- 2026-10-22, after the rebase on TASK-422 (which renamed the colliding C3 models and the route):
  - The tests were re-pointed to the new names, and the #284 xfails became passing guards.
  - pytest: 348 passed, 1 xfailed (#285).
  - vitest: 24 passed.
  - `apps/web` tsc is now clean.
  - ruff, pyright, eslint, prettier, banned_patterns and validate_docs: clean.
- 2026-10-22: fixed #285. `DecisionContextOut.value`, `DecisionOptionOut.figures`, `DecisionCardVersionOut.figures` and `DecisionRecommendationOut.reasons` are now Restricted (client figures; return information on SHL-11 g). The strict xfail is removed and the test passes.
