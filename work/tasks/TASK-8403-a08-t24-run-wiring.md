---
id: TASK-8403
title: "A-08-T24: Run wiring for AUD-12, AUD-13, AUD-26 and AUD-14"
spec: SPEC-657
acceptance_criteria: [AC-9.1, AC-9.2, AC-9.3]
risk_zone: amber
status: in-review
branch: a08-t24-run-wiring
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T24
---

## Objective
Spec section: docs/plan/epics/A-08.md §3 F2, F5, F8, F9. Run wiring: Begin and Run on AUD-12 with per-item fan-out, AUD-13 run rows (code tie-out, flux_explain, templated questions), AUD-26 run #4119, reconciliation proposal on response; C6 v2 SSE progress with polling fallback; DF-04 states; '<initiator> via Agent' attribution.

## Plan (amber)
1. Migration `0943_fieldwork_runs.py` on 0942: insert-only `fieldwork_run_rows` (kind, the runs fanned out, initiator, a code row's result, idempotency key).
2. `assurance/fieldwork_runs.py`: AUD-12 `fieldwork_attribute` per sampled item on the test's paper (registered as workpapers' test runner, so workpapers never imports assurance); AUD-13/AUD-26 tie-out (code), `flux_explain` per Unexplained line on `AN-1`, client questions (code); AUD-14 `confirmation_reconcile` on `CF-1`; run rows with C6 v2 state counts and '<initiator> via Agent'.
3. Routes: `POST /v1/tests/{id}/runs` implemented through the slot; new `fieldwork_runs_contract.py` (`POST`/`GET /v1/analytics-sets/{aid}/runs`, `POST /v1/confirmations/{cid}/runs`). DF-04 is the drafter's own 409 `drafting_not_enabled`, raised before any run row or agent run exists.
4. Web: `domain/audits/fieldwork/runs.ts` (run rows from the API, polling every 2 s while running, DF-04 detection) for the S49 screens; per-run SSE is `useRunFeed`.
5. Tests: `tests/unit/assurance/test_a08t24_fieldwork_runs.py`, `apps/web/src/domain/audits/fieldwork/runs.test.ts`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5403). Lint, pyright, tsc and eslint clean; the app imports and the three routes are in OpenAPI. Partial: AUD-13, AUD-14 and AUD-26 screens are S49 rows (A-08-T28, T29, T31), so the hooks have no live host yet; the reconciliation run starts when a person asks (an agent run is always a person's delegate, so `confirmation.responded` alone cannot start one); the drafter's fan-out is not capped at 8 in flight (each run is its own workflow on the interactive queue); run #4119's numbering is the run pane's. Gates and tests run once at the S48 end pass (build first, test last).
