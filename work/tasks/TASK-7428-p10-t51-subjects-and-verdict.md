---
id: TASK-7428
title: "P-10-T51 rest: the runtime load test's stream subjects and its verdict tool"
spec: SPEC-647
acceptance_criteria: [AC-T6]
risk_zone: amber
status: done
branch: s38-p10-t51-rest
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T51
---

## Objective
Everything P-10-T51 needs in code before its run: the 250 subjects the 1,500 streams sign in as
(the API's 6 per person, AC-T6) and a verdict tool that turns one run into the load report.

## Built
- `abacus_tools.loadtest.stream_subjects`: loads `loadtest-stream-0000…` on the synthetic firm
  only, staffed on the scenario's engagement, with the local sign-in issuer; the fleet loader's
  guards (loopback or the perf stack, no deploy in flight), one audited step each, idempotent.
- `abacus_tools.loadtest.runtime_report`: first-event p95 from the runner's report,
  commit-to-delivery p95 from the API's `realtime.delivered` lines, the 70% connection ceiling;
  Markdown table and exit code.
- RB-28's rehearsal names both. Tests: unit 9, integration 3.

## Left (P-10-T51)
The run on the perf stack and RB-28's rehearsal (the runner refuses a shared hosted build, QD-6).

## Progress log
- 2026-11-12: built and tested.
