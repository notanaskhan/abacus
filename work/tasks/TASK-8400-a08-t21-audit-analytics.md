---
id: TASK-8400
title: "A-08-T21: Audit analytics service"
spec: SPEC-657
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
branch: a08-t21-audit-analytics
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T21
---

## Objective
Spec section: docs/plan/epics/A-08.md §3 F5, §6 M7. Audit analytics service: migration, FluxAnalyticsWorkflow, stages incl. final on the adjusted layer, threshold from the materiality version with a materiality.decided subscriber, SHL-09 provenance, cited explanations, manager acceptance, templated client questions to a T-02 questionnaire with answers returning as client-answer explanations.

## Plan (amber)
1. Migration `0940_audit_analytics.py` on 0933: `analytics_sets` (status computing/current/out_of_date/superseded; one computing and one current per work item, kind, stage), insert-only `analytics_lines`, `analytics_explanations` (insert-only but the one acceptance stamp, accept-once trigger, CHECK citations >= 1 or a client answer's question, acceptor never the author), `analytics_expectations`, `prior_year_figures` (numbered imports), `analytics_questions`; `questionnaires.kind` gains `analytics_question`, `ssars_inquiry`. Registry rows in `assurance/registry.py`.
2. `assurance/analytics.py`: run, `FluxAnalyticsWorkflow` + `assurance.analytics.compute`, set view (tallies, threshold facts with the deciding partner, review hash, allowed actions), provenance, explain (422 `explanation_uncited` via `evidence.supported_citations`), accept (`not_preparer_of_target`, `seen_hash`), client questions (T-02 questionnaire, one sent question per card), `questionnaire.answered` and `materiality.decided` subscribers, prior-year figures, deterministic XLSX export; HOME-02 gate `analytics_explanation_acceptance`.
3. `analytics_contract.py` routes implemented (501 kept in `errors=`); `AnalyticsSetOut.review_hash`, `failure_code`; `change_pct` nullable; client-answer explanations may carry no citation ids. `requests.api.answer_fact`; questionnaire kind literal extended; notification `analytics_explanations_ready`; gate events in `review/gates.py`; error-code catalogue regenerated.
4. Tests: `tests/unit/assurance/test_a08t21_analytics.py`, `tests/integration/test_a08t21_analytics.py` (AC-5.3 uncited refused, AC-5.2 decided materiality = new version, old untouched). Rollback: `alembic downgrade 0933`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5400). Lint and pyright clean on touched files; the app imports. Partial: `adjustment.approved` does not exist on main, so final-stage sets are not marked Out of date when an adjustment lands; the C6 v2 SSE progress and the `flux_explain` run fan-out are A-08-T24's; the percentage leg is the 10% default until a firm threshold policy exists (A-08-T22 adds the SSARS variance policy); the generated client and `make regenerate` (route introspection, OpenAPI) run at the end pass. Gates and tests run once at the S48 end pass (build first, test last).
