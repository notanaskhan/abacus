---
id: TASK-6209
title: P-11-T34 tax form maps part 1
spec: SPEC-520  # P-11 F8 (docs/plan/epics/P-11.md AC8.4, AC8.7); SPEC-520's part 2 holds extraction
acceptance_criteria: [AC-34]  # box extraction; the row's F8 AC8.4 and AC8.7 live in the epic
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T34
branch: s31-p11-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (red)
- Box maps `evidence/forms/<form>/{2025,2026,2027}.yaml` for W-2, W-2c, 1099-INT, 1099-DIV, 1099-R,
  1099-NEC, 1099-MISC, 1099-G and 1098, family `tax_forms`; TY2026 `inherits: 2025`.
- `evidence/tax_form_rules.py`: the year on the title line, CORRECTED (the word alone, or the
  caption with a mark), code tie-outs (ordering only; a break flags both fields).
- `form_extraction.py`: additive keys on `FormMap` (`year_after`, `corrected_anchor`,
  `tie_outs`), inheritance in `load_maps`, a title-year fallback in `identify` only for maps that
  declare it, `_tax_form_checks` after `extract`. Notice maps declare none, so the notice path
  reads the same; the notice map files are untouched.
- Tests: `tests/unit/evidence/test_p11t34_tax_form_maps.py` (end pass).
- Dark: the `tax_forms` family runs only for a `notices_tax_forms` or `all` variant.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2809 | TINs never fields; CORRECTED needs a mark; tie-outs flag, never fix | no |
