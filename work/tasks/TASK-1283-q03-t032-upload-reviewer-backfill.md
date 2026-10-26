---
id: TASK-1283
title: Back-fill TASK-058 and TASK-059, the upload reviewer (Q-03-T032)
spec: SPEC-030
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T032
branch: s9b-independent-suites
test_author: ayushkbhatia
test_session: 2026-10-26, branch s9b-independent-suites (clean session following .claude/skills/ac-test-author/SKILL.md; a scripted stand-in model only, never a real model, no evals)
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Every reviewer output shown to staff carries a verified citation or reads Uncited (INV-2) and
acceptance is a human action."

## Plan (red zone)
- **Files:** `backend/tests/integration/backfill/test_q03t032_upload_reviewer.py`, with the
  shared `backfill/q03_agent_support.py` (TASK-1282).
- **Boundary:** `create_app()` over HTTP for uploads (on the client's behalf), reads, the Board
  marker and "Review now"; the compose S3 image; every `upload_processing` activity in the
  workflow's order (extract, check, preview, words, PII scan); the relay's subscriber for
  `upload_checks.recorded`, the engagement agent's `handle` per signal, a recording Temporal
  stand-in; then the reviewer workflow's steps (`create_review_run`, `load_agent_context`,
  `review`, and `fail_run` where TASK-059 D4 says the workflow ends a run). The model is a
  scripted stand-in served on the `bedrock` route, enabled through settings only
  (`ABACUS_ALLOW_REAL_MODEL_LOCALLY`, `ABACUS_MODEL_ROUTES`, parity, catalog with pinned-shape
  stand-in IDs, provider limits), so the gateway's boundary, admission, budget and usage steps
  run unchanged. No network call, no real model.
- **Production:** none expected; ED-077/ED-078 reserved for a fix (shared with TASK-1282).
- **No migration, flag, matrix or registry edit.**
- **Rollback:** delete the test file.

## Results (36 tests, all pass)
- **AC-1:** the compiled spec equals its YAML (`AgentSpec.model_validate`), with tier small,
  escalation medium, `propose`, scope `evidence.read` + `upload_review.run`, the
  `evals/upload_review` suite, not essential; the matrix has `upload_review.run` (system, agent
  task scope), `upload_review.request` (partner, manager, senior) and a firm-only read. (2)
- **AC-2:** the document text, including an injected instruction, reaches the model only inside
  one `<untrusted name="document">` layer; the request's description sits outside it. (1)
- **AC-3 / INV-2:** a verified quote is shown with its page; a quote not in the document, or on
  the wrong page, leaves the flag recorded but hidden; a shown flag lists only its verified
  quotes; every quote is a v2 citation row by the agent, the failing one unverified (DEC-267);
  an answer outside the schema records no review and the run escalates (ADR-048). (5)
- **AC-4:** at Routine the review starts once after the checks (`upload_review:<tenant>:<version>`,
  `P-6 done`), and the same with the engagement agent off; at Advise P-6 is `skipped` and "Review
  now" (202, audited `upload_review.requested`) starts it; partner, manager, senior may ask,
  staff and reviewer 403; nothing starts while the agent is paused or with the firm's reviewer
  flag off; a scanned PDF never gets a run or a model call. (10)
- **AC-5:** at a firm that is not synthetic the gateway refuses (`DataBoundaryRefused`, audited
  `ai.boundary_refused`), no model call, no review; the run ended by the workflow reads `failed`
  with a reason. (1)
- **AC-6:** every firm role reads the review; client admin and contributor get 403 on the review,
  the Board marker and "Review now", with no quote in the body; another firm 404; a walled member
  403/404; the Board counts one flag for the flagged upload and none for the clean one; no review
  yet reads `none`. (9)
- **AC-7 / INV-1:** a review changes nothing on the evidence or the request (no decision row, no
  human-only audit action by an agent); the run acts for the engagement partner (TASK-059 D2);
  a reviewer context holding `evidence.accept` or `evidence.reject` in scope is refused both;
  the database refuses `review_decision.created` with an agent actor. (5)
- **AC-9:** one call per review, its recorded cost above zero and within the spec's $0.02. (1)

## Escaped defects
None found.

## Spec drift (followed the later decision)
| TASK | AC | The spec says | The current contract says | Superseded by |
|---|---|---|---|---|
| 058 | SPEC-030 §6.3 | invalid output ends the run `failed` | the run escalates after the repair attempt; no review is recorded | ADR-048 |
| 058 | SPEC-030 §10 | prompt `evidence.upload_review@v1` | `@v3` | SPEC-030 amendment (v2), DEC-325 (v3) |
| 059 | SPEC-030 §8 | `GET …/request-items/{item}/uploads/{version}/review` under `evidence.read` | `GET …/evidence-versions/{version}/review` under `upload_review.read`; `POST` the same path | TASK-059 D1, as built |
| 058 | Q-03-T032 acceptance | an unverified output "reads Uncited" | a flag with no verified quote is never shown; a shown flag shows verified quotes only | SPEC-030 Q3 |

## Spec gaps
- A scanned (unreadable) upload: P-6 may still start the workflow, which then creates no run; the
  test asserts the promise (no run, no model call, no review), not the start.
- AC-9's engagement daily cap: its value is not in the spec; untested here.
- AC-8 stays with `tests/unit/tools/evals/test_upload_review_cases.py` and the suite (no `make
  evals`); AC-10 with `apps/web/src/legacy/spec030review.test.tsx`.
- A walled member: 403 or 404.

## Masking branch (s9a-pii-masking)
The fixture runs the word layer and PII scan the workflow runs, and every document line is free
of account or TIN digits, so the material is the same masked or not. Run against that branch's
code on 2026-10-26: all 36 pass. Expected to keep passing after it merges; the tests most exposed
if masking changes again are AC-2 (asserts document text inside the untrusted layer) and the
AC-3 quote tests (quotes must verify on the masked word layer).

## Progress log
- 2026-10-26: suite written and run (36 pass, plus 30 of TASK-1282 in the same session); gates on
  the touched files pass. No production change.
