---
id: TASK-8053
title: "A-09-T04: group-audit glossary and status rows (DF-31), banned terms, screen contracts"
spec: SPEC-658
acceptance_criteria: [AC-0]
risk_zone: red
status: in-review
branch: a09-t04-vocabulary-contracts
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T04
---

## Objective
Status words and glossary for group audit, the banned-terms lint, and the screen contracts for
AUD-32 to AUD-35, POR-23 and the AUD-31 group renditions.

## Plan (red: protected vocabulary files)
1. **Protected** `status-vocabulary.yaml`, `glossary.md`; status codegen.
2. `copy-bans.test.ts`: "significant component", "Post to NetSuite".
3. `docs/screens/{AUD-32,AUD-33,AUD-34,AUD-35,POR-23}.md`; AUD-31 group section.
4. `tests/unit/assurance/test_a09t04_vocabulary.py`.
Rollback: revert.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built (DEC-5038). Codegen clean; eslint clean. Tests run at the end pass.
