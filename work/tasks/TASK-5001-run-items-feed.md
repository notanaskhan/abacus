---
id: TASK-5001
title: "C6 v1 run items feed (polling) with the read-time legacy adapter; live trace drawer"
spec: SPEC-318
acceptance_criteria: [AC-8]
risk_zone: amber
status: done
branch: task-5001-run-items
worktree: agentwt
created: 2026-10-25
updated: 2026-10-25
---

## Plan keys
P-09-T07 (items feed, legacy adapter), P-09-T05 (PollingRunSource core) (partial).

## Plan
- **Agents:**
  - `runs.py`: `items_for` and the pure `page_items`, which numbers items by time and answers `resync` when the client is ahead;
  - items: a tool card, `agent_activity` narration for engagement agent runs, decisions, and failure;
  - repository: `run_activity` (LIST_EXEMPT) matches activity by source event, or by the run's window plus 5 s.
- **Route:** `GET /v1/agent-runs/{id}/items?after_seq=`.
- **Web:**
  - `domain/agents/runFeed.ts`: the `applyItems` reducer and the `useRunFeed` hook (1.5 s, stops when the run ends or the tab is hidden);
  - the trace drawer: a "· live" pill, "What the agent did" narration through `narrate()` (code words only), and a trace re-read on each new item;
  - the run list refreshes while any run is active.
- **Rollback:** revert the PR. There are no migrations.

## Notes
- The engagement agent writes its activity about 10–40 ms after it closes the run, and the source event ids don't match. Hence the 5 s grace window after the finish.

- **Mistake, made twice (TASK-461, then TASK-5000):** `test_f03_status_vocabulary` reads the committed `openapi.json`, so running it before `make regenerate` passes on stale data. TASK-5000 shipped `RunWriteOut.state` as a free string, which the rule refuses: every field named `state`, `status` or `*_status` must be an enum. This task renames the mixed-object codes to `outcome` on `RunWriteOut` and `RunItemOut`. Proposed lint: check-fast should run the status-vocabulary test after check-generated.

## Progress log
- Dev smoke test, across four engagements:
  - a screener card with citations 2;
  - a matcher card with proposals 3;
  - an upload reviewer card with flags 2;
  - a failed screener card plus `internal_error`;
  - an engagement agent card plus the "reminders.sent" and "digest.sent" narration.
- On every run, `after_seq=last` returns nothing and `after_seq>last` answers `resync`.

## Definition of done
- [x] test_runs, classification, status vocabulary, api, route introspection and matrix tests pass.
- [x] runFeed (3), spec318runs (7) and spec027agent pass.
- [x] check-fast passes.
