---
id: TASK-317
title: "F-02-T07 to T10: glossary identifier rule L12, scope guards, the 13-item nav and the banned-terms lint"
spec: SPEC-306
acceptance_criteria: [AC-1]
risk_zone: red
status: done
branch: task-317-guards
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **T07, rule L12** in `banned_patterns.py`.
  - The ban list is generated from the glossary's "Don't use" columns (`glossary_bans`).
  - It checks class names (as snake_case), top-level function names and table names (whole, singular or first word) under `src/abacus/modules`.
  - Locals stay out: the bans name concepts, and words like `email` are fine as variables.
  - The 26 names already in use are dated legacy exceptions, each naming the task that renames it.
- **T08, `docs/architecture/scope-guards.yaml` and `abacus_tools.quality.scope_guards`** (in check-fast):
  - **Contents:** the nav, excluded identifiers (D6, D10, X-01 to X-08), the single-audit allowlist, and banned terms.
  - **Matching:** whole identifiers, never substrings, in Python string constants and names (not comments or docstrings), migrations, the matrix, flags, the registry, prompts and seed.
  - **Eval suites:** checked for excluded identifiers only, because their cases are adversarial data, not product text.
  - **Generated:** `packages/ui/scope-guards.gen.json`, checked for drift.
- **T09, the bar and the lint**:
  - `apps/web/src/shell/nav.ts` holds the 13 areas, with a test for order and for no badge or count;
  - `packages/ui/eslint-scope-rules.js` bans terms in literals, JSX text and templates, in both apps/web and packages/ui.
- **T10:** the false-positive corpus (agricultural, security, CMMC readiness, GAAS nonissuer, "‹person› via Agent", reviewer, Brightwater Hale) raises nothing. The L12 and scope-guard tests pass.

## Not done
- T07's ADR decider checks (both founders' handles). The solo edition (SU-06) voids the two-founder approval clause.
- "Accrued" is not added as a required word. The founder keeps "Abacus" as the product name in this stream.

## Definition of done
- [x] 20 guard tests and the nav test pass.
- [x] apps/web and packages/ui lint clean.
- [x] check-fast passes.
