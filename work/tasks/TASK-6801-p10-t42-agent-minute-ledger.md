---
id: TASK-6801
title: "P-10-T42: Agent-minute ledger consumer and rollups: agent_run.completed to agent_minute_ledger (round-half-up of agent_ms / 60,000 stored once), engagement and firm usage-month rollups over stored integers, GET /v1/firm/usage and GET /v1/engagements/{id}/effort"
spec: SPEC-647
acceptance_criteria: [AC-M1, AC-M2, AC-M3, AC-M4]
risk_zone: amber
status: in-review
branch: s36-p10-t42
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: P-10-T42
---

## Objective
ADM-14's 14,920 and ENG-06's 412 = 46 + 24 + 342 foot from the seed ledger, and a sub-30-second
run posts 0 minutes but counts as a run.

## Plan (amber: written before the build)
1. **Migration 0810** (on 0801): `agent_minute_ledger.run_number` (bigint, null), insert grant;
   registry INSERT_COLUMNS. Expand-only; downgrade drops the column.
2. **Agents (posting):** `complete_run_activity` locks the run, stores `agent_minutes` once at the
   first terminal state (round-half-up of `agent_ms ÷ 60,000`, `platform.api.agent_minutes`) and
   emits `RunCompleted` (`agent_run.completed`: run, state, business date, ms, minutes, capability,
   service line, engagement, number, definition, work item, cost as a string). A second terminal
   write keeps the minutes and emits nothing.
3. **Platform (`metering.py`):** the subscriber writes one insert-only ledger row per run
   (`ON CONFLICT (tenant_id, run_id) DO NOTHING`) and adds the same integer to the usage month's
   rollup; audit `agent_minutes.posted`. Usage month: day 15 to day 14 (`2026-09` = Sep 15 – Oct 14).
   `record_synthetic_minutes` (synthetic firms only) is the seed's path through the same code.
4. **Reads:** `GET /v1/firm/usage?month=` (`usage.read`; the month's minutes by service line,
   engagement and capability; included minutes = the firm's entitlements' allowances) and
   `GET /v1/engagements/{id}/effort` (`engagement.read`; one line per completed run, budget,
   run count). Both behind `agent_runtime.v2` (off: 404); client principals 404; no USD.
   Engagement and capability names come from labellers the engagements and agents modules
   register (ADR-008); engagements the reader may not see fold into "Other engagements".
5. **Seed:** `--slice agent_minutes` (`usage_slice.py`): ENG-06's #4019, #4064, #4102 (412, usage
   month `2026-08`), ADM-14a's five service-line totals for `2026-09` (14,920) and 20,000 included.
6. **Tests:** `tests/unit/platform/test_p10t42_metering.py` (rounding, months, payload, seed
   figures); `tests/integration/agent_tests/test_p10t42_agent_minutes.py` (ADM-14a and ENG-06a
   over HTTP, redelivery, synthetic-only, sub-30-second run, stored once, open run, 403, flag off).
7. **Rollback:** revert the PR; 0810's downgrade drops the column (no rows depend on it).

## Progress log
- `2026-11-11` — Built (S36, build first): migration 0810, `platform/metering.py`, the routes,
  the agents event and completion, labellers, the `agent_minutes` slice, tests written; not run
  (end pass).

## Partials
- v1 specialist runs (status-only, no `agent_ms`) are not metered: the ledger covers v2 runs.
- ADM-14a's September month is posted as one "Earlier runs" (`history`) line per service line:
  the handoff gives that month by service line only, so by-capability for it is that one line.
- Two of ENG-06's capability codes (`requests.pbc_list_builder`, `ebp.provisions_extractor`) are
  history-only: no spec defines those agents yet (K-03/W-03 define the library).
- Usage alerts, overage and ADM-14's screen are G-04's; ENG-06's screen is I-04's.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3401 | Posting, usage month, labels, reads, seed | no |
