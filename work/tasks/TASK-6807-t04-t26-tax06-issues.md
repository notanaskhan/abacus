---
id: TASK-6807
title: "T-04-T26: TAX-06 Issues states a-g in fixture mode on T9 issues-individual"
spec: SPEC-649
acceptance_criteria: [AC-4.1, AC-4.2, AC-4.3]
risk_zone: green
status: in-review
branch: s36-t04-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-04-T26
---

## Objective
TAX-06a-g render from scenarios, Accept on the box 18A ghost values opens SHL-10 and Issues go 4 to
3 after approval, and Mark as Resolved is disabled with 'Resolves when the final K-1 is released'
on the Draft K-1 issue.

## Built
`apps/web/src/screens/TAX-06/` (`copy.ts` verbatim from the handoff, `Issues.tsx`, `index.tsx`,
`TAX-06.test.tsx`): category-path queue with severity flags and the agent-can-fix glyph, detail KV
and What it blocks band, three-way lighting (chip, viewer region, two ghost fields) through the
match tokens, Accept to the host (SHL-10) and Reject with a reason, Set Fix Instructions with the
suggested instruction (SHL-15), Explain…, Mark as Resolved with a required note (disabled with its
reason on the Draft K-1 issue), Ask the client…, Resolved filter, empty state, loading, CSV with
formula-safe cells. Screen contract states move to fixture.

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- The gallery frame and parity measurement for TAX-06 wait for the end pass's visual run.
- Live data (RW-1 issues routes, SSE) is T-04-T29's swap.
