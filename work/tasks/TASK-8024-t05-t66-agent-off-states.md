---
id: TASK-8024
title: "T-05-T66 part 1: agent-off states, the shared gate and TXP-01"
spec: SPEC-651
acceptance_criteria: [AC-13]
risk_zone: green
status: in-review
branch: t05-t66-agent-off-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: T-05-T66
---

## Objective
With agents off, every TXP screen completes the J08 P0 steps by hand, and no control offers a refused action (T-05 §F13).

## Plan
1. [x] `domain/tax/agents.ts`: `entityAgentGate(caps, capability)` from `GET /v1/agents/capabilities`. It fails closed while loading, puts the reason codes in words, and marks §7216 refusals as consent. `PREPARED_WITHOUT_AGENTS`. Tests in `agents.test.ts`.
2. [x] TXP-01: Regenerate is offered only when `tax.memo_drafter` is available. Otherwise a note reads "Prepared without agents · <reason>" (`Summary.tsx` reads the capabilities). Test in `TXP01.test.tsx`.
3. [x] TXP-02: the mapper suggestion (`tax.account_mapper`). With agents off, "Map…" stays the person's picker and no suggestion is offered.
4. [x] TXP-06: the agreement reader's proposal (`tax.agreement_reader`). The structure is keyed by hand.
5. [x] TXP-10: Set Fix Instructions (`issues.fix_runner`).
6. [x] TXP-00: the waiting-on-inputs notice naming the consent, read from the run step's wait reason.
7. [x] Entitlement-locked card on the coordination view (`tax.entity_returns` refused).
8. [x] Flag-off reachability across the eight routes.

## Progress log
- `2026-11-14` — Part 1 (steps 1–2) built. eslint and tsc clean; vitest at the end pass. The note sits in TXP-01's row frame. Check its placement against TPL-09 at the parity run (the state is undesigned, T-05-T03).
- **Partial.**
  - Steps 3–8 remain.
  - The capabilities are read firm-wide (no `engagement_id`), so a §7216 refusal shows only where the server reports it at firm level. The per-client consent words ("§7216 AI consent — Ridgeline (1 of 2 signed)") need the engagement-scoped read, which TXP-01's route params do not carry yet.
- `2026-11-15` — Steps 3–8 built in TASK-8073 (DEC-5059), with the engagement-scoped gate.
