---
id: TASK-7526
title: T-04-T46 fixture-to-live swap and TAX-02's post-window wiring
plan_key: T-04-T46
spec: SPEC-649  # T-04 AC-13.2; TAX-08, TXI-02, TXI-03
acceptance_criteria: [AC-13.2]  # on staging Samuel asks, approves and undoes within 10 s; the Apr 27 train changes no live behaviour while the flags are off
risk_zone: green
status: in-progress
branch: t04-t46-live-swap
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The post-window frontend wiring: TAX-02 Run draft / Re-run draft and the shared return-frame tabs,
and the fixture-to-live swap of TAX-08, TXI-02 and TXI-03 (SseRunSource with polling fallback).

## Plan (built)
- `apps/web/src/screens/TAX-02/index.tsx`: Run draft calls `draftRunMutation` (T-04-T55's route)
  when the record's `allowed_actions` include `tax_return.draft_run` and `tax_agents.enabled` is on;
  otherwise the planned disabled button in fixture builds only, as before. The Review, Issues and
  Activity tabs follow the record's `tabs` (the server's registry, T-04-T55): live when listed,
  planned otherwise. With the flags off nothing changes.
- Test `TAX-02.t04t46.test.tsx`.

## Partial
- TAX-08's live drawer landed in S37 (TASK-7323, #1740). TXI-02's and TXI-03's live hosts (their
  `SseRunSource` over the run's events with polling fallback) and the staging walk ("Samuel asks,
  approves and undoes within 10 s") need staging; the hosts stay in fixture mode here.
- Re-run draft… on a drafted return reuses the same mutation once TAX-04's draft history lands.

## Progress log
- `2026-11-12` — TAX-02 wiring built (DEC-4526); the staging swap remains. Tests run at the end
  pass.
