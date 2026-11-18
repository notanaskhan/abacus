---
id: TASK-8624
title: "C-02-T15: Screen contracts and scenarios for CLS-07, CLS-08, CLS-11, CLS-12, CLS-13"
spec: SPEC-700
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: c02-t15-contracts-scenarios
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: C-02-T15
---

## Objective
Spec section: docs/plan/epics/C-02.md §2.1, §5. Screen contracts for the five C-02 screens and scenarios for all 37 artboards with persona, clock and snapshot (E0 9:24 AM CDT to Tue Jan 26, 2027 CST).

## Plan (green)
1. docs/screens/{CLS-07,CLS-08,CLS-11,CLS-12,CLS-13}.md: header, every artboard and the handoff links, keeping C-02-T10's design deltas.
2. apps/web/src/fixtures/scenarios/CLS-*.ts: 37 states with persona and offset instant (CDT until Nov 1, CST after), E0 handlers with closes.engine and adjustments.posting on; screens/<ID>/scenarios.ts re-exports.
3. fixtures/scenarios/c02-scenarios.test.ts: 9 + 8 + 8 + 5 + 7 states, seated personas, offset instants.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5624). Partial: per-state data handlers and copy.ts join with each screen task (data from the Python scenario via make fixtures, never hand-written); the /components routes open once each screen component exists (CLS-07 in C-02-T17). CLS-13c's README viewer cell names the vendor string, not a person: the state is Raj Malhotra's. Gates and tests run once at the S50 end pass (build first, test last).
