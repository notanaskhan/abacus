---
id: TASK-7930
title: I-02-T13 rest: staleness asks for a background rebuild
plan_key: I-02-T13
spec: SPEC-654
acceptance_criteria: [AC-F3]
risk_zone: red
status: in-review
branch: i02-t13-staleness-poll
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish I-02-T13's staleness partial: the Today read flags ready briefs whose why lines name gates closed since, the panel says so and requests a debounced background rebuild of those engagements only.

## Done
- `agents.api.briefing_why_gone(blocks, open_gates)`; the assembly lists `stale_engagements` (ready briefs naming a closed gate).
- `POST /v1/me/today/builds` takes `mode: background`: only the stale engagements, through `ensure_briefings(..., "background")` (debounce 15 minutes, six a day, three at once: T13's own rules).
- FE: `useStaleRebuild` asks once per (date, stale set) from HOME-05's docked panel and drawer; SHL-23's footer adds "Written {time} · items changed since".
- Tests: `why_gone`; the route builds only the stale engagement in background mode; the panel's note.

## Partial
- No server-side schedule: the poll is the open panel's refetch (DEC-4926). P-50 (kernel schedules) lands at S62.

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4926 Staleness rebuilds are asked by the open Today panel, not a server schedule | No brief is built for someone not looking (budget); P-50 schedules are S62 | no |
