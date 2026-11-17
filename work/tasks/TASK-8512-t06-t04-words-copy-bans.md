---
id: TASK-8512
title: "T-06-T04: Glossary, status vocabulary and copy-lint bans for entity depth"
spec: SPEC-702
acceptance_criteria: [AC-26]
risk_zone: red
status: in-review
branch: t06-t04-words-copy-bans
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T04
---

## Objective
Spec section: docs/plan/epics/T-06.md §4.9. Status rows (hand-off, sourcing position, PTET election, §754 decision, form diagnostics), glossary rows, copy-lint bans ('Export for Tax', partnership words on 1120/990 frames, 'QIP' on the Elm Street roof, '$' in statement grammar).

## Plan (red)
1. status-vocabulary.yaml: tb_handoff (Not available, Needs review, Ready derived; Handed off; Superseded), sourcing_position, ptet_election, section_754_decision, form_diagnostic; regenerate _statuses.py and status.gen.ts.
2. glossary.md: TB hand-off, external party, sourcing position, PTET election, §754 decision, form preview, relationship graph layout.
3. L2 (`apps/web/src/copy/registry.ts` lintCopy): export-for-tax, qip-roof (TXP-03), partnership-word (TXP-13 form1120./form990./provision./functionalExpenses. keys), statement-dollar (T-06 screens, statement keys); deny-case fixtures in copy-registry.test.ts.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5512). Codegen clean; copy-registry vitest 11 passed (run once: cheap); banned_patterns clean. Gates and tests run once at the S49 end pass (build first, test last).
