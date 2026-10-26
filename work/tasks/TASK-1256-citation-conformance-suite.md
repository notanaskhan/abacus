---
id: TASK-1256
title: Code-only citation conformance suite and citation_region_resolved (P-03-T17)
spec: SPEC-322
acceptance_criteria: [AC-38, AC-39, AC-40]
risk_zone: red
status: in-review
epic: P-03
plan_key: P-03-T17
branch: s9a-pii-masking
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Fabrication caught and valid citations accepted are both 1.0 on the seeded set, and no existing
threshold is lowered."

## Plan (red zone)
- **Suite `evals/citations/suite.yaml`:** code-only and deterministic, with no model and no
  containers. It copies the shape of `evals/agent_blocks` (TASK-5006): `required_pass_rate` 1.0,
  `repeats` 3, and one `expect` per case (`pass` or the verification reason, or `moved`).
  - The seeded document: three pages of words with boxes, one of them a W-2 line with the SSN
    region.
  - Categories: `fabricated_page`, `fabricated_bbox`, `fabricated_quote`, `fabricated_value`,
    `unicode` (homoglyph, bidi and zero-width fabrications), `moved`, `masked_quote`, `valid` and
    `containment` (no unmasked TIN in the material built from the seeded page and sheet).
  - Metrics: `fabrication_caught`, `valid_citation_accepted`, `masked_quote_verified` and
    `tin_in_agent_material`, each 1.0.
- **Code under test:** a pure `verify_layer_page` is lifted out of `verify_document_text` (the
  layer branch: page lookup, the masked projection, `verify_on_layer`), so the suite drives the
  verifier's own code. Moved cases use `citations.display.state_of`. Containment uses
  `masking.masked_words`, `pii.masked_rows` and the kernel TIN scrub, as agent material does.
- **Gate:** `tests/unit/evidence/test_citations_suite.py` checks each case, a score of 1.0 on
  every repeat, the four metrics at 1.0, and covered categories. Seeded regressions: turning off
  the masking, the box check or the value check must drop the score. It runs in the fast unit
  stage.
- **Report-only metric `citation_region_resolved`:** the share of a run's verified
  `document_text` citations that carry a bbox (vacuous 1.0). It is added to the screening,
  upload_review and matching `METRICS`, observed per attempt from `citations` by
  `created_by_run_id`, and declared in each suite under a new `reports:` list. Each schema
  validates that list: a known metric, never also a threshold. No threshold changes, and no
  suite version bump (the case sets are unchanged, so Q-02 clearances keyed by version stand).
  The eval runners also run the word layer and PII scan before the reviewer and matcher, which
  read only masked material since P-03-T15. `make evals` is not run (it costs money).
- **Rollback:** revert.

## Progress log
- 2026-10-26: plan written.
- 2026-10-26: built as planned. `test_citations_suite.py`: 39 tests (29 cases, the score on
  every repeat, the four metrics at 1.0, coverage, and 4 seeded regressions).
  `test_citation_region_metric.py`: 4 tests, including that every threshold equals its value
  before this task. Region counts are kept out of the signed case rows, because adding them
  broke `test_evals.py` (summary canonical bytes). Targeted runs: verifier, masked-rendition,
  agent-citation, moved and read integration plus evidence and evals unit, 586 passed; tools
  unit, 542 passed. `make evals` was not run (it calls real models), so the model suites' new
  report is unexercised end to end.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-371 | The conformance suite's cases and categories, the unicode reading and the report-only declaration | No |
