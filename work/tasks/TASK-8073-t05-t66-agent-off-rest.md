---
id: TASK-8073
title: "T-05-T66 rest: agent-off states on TXP-02, TXP-06, TXP-10 and TXP-00, the locked entitlement, flag-off reachability"
spec: SPEC-651
acceptance_criteria: [AC-13]
risk_zone: green
status: in-review
branch: t05-t66-agent-off-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: T-05-T66
---

## Objective
Steps 3–8 of TASK-8024 (T-05 §F13; SPEC-651 AC-13.1 to AC-13.3).

## Built
- **Engagement-scoped gate.** `domain/tax/useEntityAgentGate(returnId, capability)` reads the
  return's engagement and asks `GET /v1/agents/capabilities?engagement_id=`, so a §7216 refusal
  is this client's, not the firm's. It fails closed while loading. A shared `AgentsOffNote`
  renders "Prepared without agents · ‹reason›" (TXP-01's note).
- **Step 3, TXP-02:** with the mapper (`tax.account_mapper`) off, "Map…" stays the person's
  picker and the screen says why.
- **Step 4, TXP-06:** with the agreement reader (`tax.agreement_reader`) off, the structure is
  keyed by hand and the rail says why. Approve structure stays the person's.
- **Step 5, TXP-10:** fix instructions (`issues.fix_runner`) render disabled with the reason. They
  are also disabled while the capabilities load, never hidden.
- **Step 6, TXP-00:** the run row carries `waiting_on`, read from the run's `blocked_on.needs`
  through `agents.work_item_runs`. Frame D reads "Waiting on this client's §7216 AI consent" when
  that is the wait.
- **Step 7:** web `MODULES` gains `tax_entity_returns` and `cas_closes` (the latter closes
  C-01-T12's note). Without `tax_entity_returns`, an entity return opens the coordination view
  (TAX-02) under a locked card, and no workbook pane renders. The fixture firm holds both modules.
- **Step 8:** with `tax.entity_workspace` off, every entity route draws its own screen. This is
  tested across the slugs.
- Tests: `apps/web/src/screens/TXP-00/t05t66-agent-off.test.tsx`.

## Partial
- The copy is T-05-T03's undesigned set (no artboard). Its placement is checked at the T-05-T69
  parity run.
- T-05-T68 (J08 Playwright P0) and T-05-T69 (parity, accessibility, INP) are unblocked.

## Progress log
- `2026-11-15` — Built (DEC-5059). tsc, eslint and prettier are clean; vitest runs at the end pass.
