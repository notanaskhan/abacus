---
id: TASK-7805
title: "Q-03-T148: supply-chain hygiene 2027 Q3: scans, CodeQL triage, three linear regexes"
spec: SPEC-000  # row (Q-03-T148; ADR-099; DEC-366)
acceptance_criteria: [AC-20]  # the row's acceptance, below
risk_zone: red
status: in-review
branch: lo38-q03-t148-supply-chain
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
plan_key: Q-03-T148
---

## Objective
"No high or critical dependency or image finding is older than its SLA at the quarter's end."

## Plan (red)
- Run pip-audit, bandit and pnpm audit locally, and read CI's `security.yml`, code scanning and
  Dependabot.
- Fix the CodeQL true positives with equal-behaviour rewrites:
  - `evidence/export_download._RANGE`: possessive quantifiers;
  - `reporting/templates.has_markup`: opener plus one `>` lookup;
  - `assurance/governance_comms._AMOUNT`: a search-equivalent pattern.
- Tests: `tests/unit/quality/test_q03t148_linear_regexes.py` (Hypothesis against the old patterns
  and a time bound). The existing range and letters suites pass.
- Record the quarter, the register entries and DEC-4802. No migration, flag or route.
- Rollback: revert the commit (the old patterns were correct, only slow).

## Security review (inline, red diff)
- The three changes only narrow the time; each accepts exactly the old inputs (property-checked).
- `has_markup` still refuses every tag the old pattern refused, so no firm wording that was refused
  before is now let through.

## Open
- js-yaml (due Dec 3): override decision.
- zlib1g base digest (due Dec 7): let the weekly refresh open PRs, or open one by hand.
- Dismiss the 18 false positives in code scanning (the user's call).
- uv.lock refresh; Inspector.

## Progress log
- 2026-11-12: run and fixed; tests pass.
