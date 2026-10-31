---
id: TASK-2702
title: P-04-T54 SHL-15 Issue composer and fix instructions
spec: SPEC-000  # P-04-T54 row, P-04 §3 F7 and docs/screens/SHL-15.md
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-04
plan_key: P-04-T54
branch: s22-p04-t54
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "SHL-15b sends only the client wording to POR-04, the propose-only checkbox is
  absent, and a-prime, a-double-prime and d render from scripted fixtures."

## Scope
**In**: `screens/SHL-15` (fix instructions, new issue, bulk, the T9 detail block), `domain/review/issues.ts`,
`?ov=issue:` registration and builders, manifest `fixture`, fixtures (Feld's four issues, b/c
drafts, a″ proposal, teams, contact), gallery artboards, tests, `docs/screens/SHL-15.md`.
**Out**: fix runner (P-10, T-04), hosts (TAX-06, TXP-10, AUD-15) that mount the detail and open
the sheet, Mark as Resolved and Explain… controls (hosts), `review.issues` flag.

## Plan
1. Tests first (`SHL-15.test.tsx`): a (card, suggestion via AgentText, Use suggestion, scope, POST
   body, no checkbox), agents-off 409, b (send body keys exactly, Idempotency-Key), c (4 → 5,
   Review point), e (bulk body), a′, a″ (ghosts, Accept → `?ov=approve:`), d (citations, no control).
2. Build on the generated client. Rollback: revert.

## Progress log
- `2026-10-31` — built; tsc, eslint, prettier clean on the touched files. Tests run at the S22 end review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1752 (overlay refs, flag, plain text, send body) | contract and DF-13 | No |
