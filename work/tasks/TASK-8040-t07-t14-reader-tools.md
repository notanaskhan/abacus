---
id: TASK-8040
title: "T-07-T14: tax tools for the instrument reader (C17) and the determination applier"
spec: SPEC-656
acceptance_criteria: [AC-1.4, AC-2.1, AC-2.2, AC-2.3, AC-2.4]
risk_zone: amber
status: in-review
branch: t07-t14-reader-tools
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T14
---

## Objective
Three C17 tools for the reader (two reads, one propose) with their description prompts, and the
suggestion applier for `instrument_determination`.

## Plan (amber)
1. `tax/instrument_tools.py`: `tax.read_instrument_clauses`, `tax.read_trust_facts`,
   `tax.propose_trust_determinations`, `apply_determination`; registered from `tax/api.py`.
2. Prompts `ai_gateway/prompts/tool.tax.{read_instrument_clauses,read_trust_facts,
   propose_trust_determinations}/v1.txt`.
3. `evidence/region_text.py` + `evidence.api.masked_region_text`.
4. Tests: `tests/unit/tax/test_t07t14_instrument_tools.py`.
Rollback: revert.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (TASK-8029).
- `2026-11-15` — Built (DEC-5026). Not run (end pass).
- **Partial.** The tools run only inside T-07-T13's capability; the database path of a proposal
  (citations recorded, the proposal and its adoption) runs in the end pass's integration suite.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5026 | Masked clause text; number provenance by fact id; refuse whole; field_key convention | no |
