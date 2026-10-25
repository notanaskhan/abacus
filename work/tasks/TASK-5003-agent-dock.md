---
id: TASK-5003
title: "SHL-13 agent dock, first slice: runs as tool cards in the audit cockpit's Agent tab"
spec: SPEC-318
acceptance_criteria: [AC-10]
risk_zone: amber
status: done
branch: task-5003-agent-dock
worktree: agentwt
created: 2026-10-26
updated: 2026-10-26
---

## Plan keys
P-09-T09 (SHL-13 dock host), P-09-T13 (Open trace from the dock) (partial).

## Plan
- **`domain/agents`:**
  - `AgentDock.tsx`: tool cards with live expansion through `useRunFeed`, plus Open trace;
  - `TraceDrawer.tsx`: WB-09, moved from `legacy/AgentRuns`, with its own step-up slot like ADM-01, because domain code may not import `shell/` or `api`;
  - `narrate.ts`: the activity wording, moved from `legacy/AgentActivity`;
  - `index.ts`: the public entry.
- **AUD-02:** the Agent tab mounts `AgentDock`, with the existing `AgentActivityTab` as its children. The DockHost comment reserves this mount for P-09.
- **Fixtures:** `audits.ts` answers the runs list with `options.agentRuns`, empty by default. No invented runs.
- **Rollback:** revert the PR.

## Notes
- No approve or decline controls. P-09-T14 binds them to P-10's C6 v2 routes, and the C3 proposals routes are still stubs in the cofounder's P-04 lane.

## Progress log
- AgentDock (4 tests), spec318runs and spec027agent pass, and so do the AUD-02, AUD-03 and audits domain tests (39).

## Definition of done
- [x] Web tsc, eslint and targeted vitest pass.
- [x] check-fast passes.
