---
id: TASK-8760
title: "Q-03-T347: M19 and M20 quality evidence: consolidation goldens, portal-scope isolation extended to component auditors and pen-tested, I-CONFIRMATION-ISOLATION green, close goldens, QBO suite green for 30 nights"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s51-q03t347
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-03-T347
---

## Objective
Both founders sign before Fri Sep 29 and Tue Oct 31.

## Plan (amber)
1. Run the offline evidence: consolidation goldens, close goldens, confirmation isolation, component-auditor isolation.
2. Read the QBO conformance nightly history (connectors-nightly.yml).
3. Record the evidence and the gate reading in `docs/plan/status/Q-03-M19-M20-evidence.md`, with an empty signature table.
4. Rollback: revert the PR (docs only).

## Progress log
- `2026-11-20` — 59 evidence tests pass locally; the QBO nightly is 21 of 21 green from 2026-10-30 to 2026-11-19, short of 30 nights; the pen test is deferred (DEC-1389). Not done: the founders' signatures are theirs. Gates and tests run once at the S51 end pass (build first, test last).
