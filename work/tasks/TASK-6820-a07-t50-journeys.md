---
id: TASK-6820
title: "A-07-T50: journey E2E for J03 9b and 15-19, J18 5-6, J04 12 and 14-16, J05 6 (fixme until A-08)"
spec: SPEC-644
acceptance_criteria: [AC-50]
risk_zone: green
status: in-review
branch: s36-a07-t50
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T50
---

## Objective
J03 steps 15-19 and J18 steps 5-6 pass on staging with every invariant asserted and axe clean.

## Built
- `apps/web/e2e/journeys/a07-support.ts`: gallery artboard URL, owner annotation, screen root,
  and `noAgentDecision` (INV-1: no agent-owned control carries Approve, Sign off, Release, Send,
  Post, Decide, Concur or Lock).
- `J03-ebp-audit.spec.ts`: the six A-07 §10 tests (9b, 15, 16, 17, 18, 19), each step on its
  artboard with the screen's verbatim copy; the harness runs axe and INV-1 to INV-5 after each.
- `j18-audit-quality.spec.ts`: j18 5-6 (G6, G8, G9, only Post-lock addition offered) and the
  server's archived refusal (full-stack only).
- `J04-fs-audit.spec.ts`: j04 12 (AUD-19 e, Granite's going-concern question); j04 14-16 fixme with
  its owner (Granite's release and archive are not drawn on AUD-24/25; staging walk on PF-X1).
- `J05-ssars.spec.ts`: j05 6 fixme naming A-08's AUD-26 (ADR-079: no skip without an issue).

## Partial
- Fixture project only for now. Full-stack and staging are fixme with A07_LIVE until the S36 batch
  deploys and `audits.letters`, `audits.report_release` and `audits.archive` are on for PF-X1. The row's
  "pass on staging" needs that deploy (and staging, still not up).
- j04 14-16 needs a Granite Peak release and lock on staging.
- Prettier and ESLint run at the end pass (this worktree has no node_modules yet).

## Progress log
- `2026-11-11` — Built (S36). Specs written, not run (end pass).
