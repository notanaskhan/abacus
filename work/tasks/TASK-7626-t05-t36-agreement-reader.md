---
id: TASK-7626
title: T-05-T36 tax.agreement_reader capability (spec v2 workflow, medium tier)
plan_key: T-05-T36
spec: SPEC-651
acceptance_criteria: [AC-F5]  # straight percentage, monthly interim closing, LPA §4.1 + Assignment §3; suite passes
risk_zone: red
status: in-review
branch: t05-t36-agreement-reader
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The agreement reader: clauses in, a proposed allocation structure out, every parameter cited and
verified by code, the §706(d) question raised when the agreement is silent or conflicting,
propose-only.

## Plan
- `tax/agreement_reader.py` (new): input and output schemas (no action field), `settle` (quote
  verification, number provenance, code's convention reading), `read_agreement` (gateway call
  with untrusted clauses and the partnership's §7216 subjects, then C17 propose).
- `tax/tools.py`: `tax.propose_allocation_structure` (propose, `tri`).
- Prompts `ai_gateway/prompts/tax.agreement_reader/v1.txt`,
  `tool.tax.propose_allocation_structure/v1.txt`.
- Spec `agents/specs/v2/tax.agreement_reader.yaml`; `_specs_v2.py` regenerated.
- Test `backend/tests/unit/tax/test_t05t36_agreement_reader.py`: the frozen suite's cases settled
  and graded by `abacus_tools.evals.tax_entity.reader_grades`.
- Rollback: revert; no caller reaches the capability yet.

## Security notes (red)
- Clause text goes to the model only inside the untrusted block; nothing the model returns is
  shown unverified; numbers the clauses do not contain are dropped.
- No new matrix action: the tool uses `proposal.create`; the agent's task scope reads the return
  and the structure only.

## Partial
- Reading the LPA and assignment from evidence (clause segmentation of the document's text
  layer) and writing `document_text` citation rows with bbox for SHL-08's lit clause are carried
  to T-05-T41 (adoption of the reader's proposal). The caller supplies clause id and text.
- The `interim_closing_706d` run step still answers `import_required` until T-05-T40 calls it.
- Prompt variant flag and suite registration in `_eval_suites.py` are T-05-T47.

## Progress log
- `2026-11-12` — Capability, tool, prompts and spec built (DEC-4621). Tests at the S40 end pass.
