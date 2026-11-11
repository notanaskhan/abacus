---
id: TASK-7307
title: "T-05-T16: Property tests (Hypothesis) for E1, E5, E6 and E13: footing, conservation to 100.000000%, idempotence on inputs_hash, Σ K-1 = K for random structures, DAG acyclicity and dirty-set minimality, export-to-parse round trip; mutation floor wired for tax/compute/entity and workpapers/compute"
spec: SPEC-651
acceptance_criteria: [AC-0]  # the spec's section ids (validate_docs reads AC-<n>)
risk_zone: amber
status: in-review
branch: s37-t05-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T16
---

## Objective
The property suites run in stage 2 and the nightly mutation job reports a killed ratio for both
compute packages.

## Plan (amber)
- `backend/tests/property/tax_entity/test_t05t16_entity_properties.py`: E5 allocation (every
  period and partner split foots, interests conserve to 100.000000%, idempotent hash), E5 waterfall
  (every check foots, Σ plugs = income), E6 (Σ K-1 = K, Item K foots, one K-1 per partner), E1
  (every column foots, idempotent hash).
- `backend/tests/property/workpapers/test_t05t16_workbook_properties.py`: E13 order respects
  every read, dirty set = transitive dependents (minimal), recompute = full evaluation, a back
  reference is a cycle, render-then-parse round trip.
- Mutation: `abacus_tools.quality.mutation.SCOPES["compute"]` is `src/abacus/*/compute/*.py`,
  and `fnmatch`'s `*` crosses `/`, so `tax/compute/entity/*.py` and `workpapers/compute/*.py` are
  already in the nightly and weekly runs; no protected edit. The `compute` floor stays 0 until the
  weekly run's first baseline (raising it is AY's, per `mutation-thresholds.yaml`).
- Rollback: revert.

## Progress log
- `2026-11-12` — Built (S37). Ruff clean; suites written, run at the end pass.
