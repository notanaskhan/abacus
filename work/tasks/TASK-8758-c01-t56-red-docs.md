---
id: TASK-8758
title: "C-01-T56: Red docs: RB-04 addendum (hourly sync outage and catch-up), runbook 'Intuit meter budget exhausted', connections and ledger READMEs, .claude/skills/connector update with your approval, final C9 v2.1 contract doc"
spec: SPEC-655
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s51-c01t56
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-01-T56
---

## Objective
Both runbooks are rehearsed once on staging and the skill update merges with your approval.

## Plan (red)
1. RB-04 addendum: the hourly close sync (scope, business hours, kill switches), recognise, contain, catch-up after recovery (CDC bounds it; reauth and meter pauses stay), never re-run tasks to refresh.
2. RB-94 `docs/runbooks/intuit-meter-budget.md`: what pauses, Sync now still runs and clears the pause, next-month recovery (a Sync now per paused entity, because ticks skip paused schedules), raising a budget only with the firm's written agreement as a reviewed platform change (no route edits it in v1).
3. connections README: the hourly sync section; ledger README: C9 v2.1; c09-ledger.md v2.1 marked final for C-01 (shapes unchanged).
4. Proposed `.claude/skills/connector/SKILL.md` addition, NOT applied (protected; needs Ayush's approval): a section 'Hourly sync for a consumer' — register a sync scope through kernel.sync_scope (the connector never imports its consumer), read the flag and kill switch past the cache before any credential, meter before the call and pause scheduled ticks at the budget while a person's on-demand pull still runs, CDC since the schedule's cursor and only the changed datasets a month at a time, record immutable snapshots, codes only, and the route name rule (`ledger-pull`, DEC-5015). The temporal-workflow skill gets the loop-of-identifiers note (every rule in the activity module).
5. Rollback: revert the PR (docs only).

## Progress log
- `2026-11-20` — Written, stacked on #2396; validate_docs passes. Not done: neither runbook is rehearsed on staging (needs a staging tenant with the fake QBO and a small budget); the skill update is drafted in this file and waits on Ayush's approval (protected path); the failure-rate and meter-budget alarms the runbooks name are C-01 §10 item 6 and not built, so RB-94 lists no alarm and RB-93 lists SLO-09 only. Found while writing: a meter pause is cleared only by an on-demand Sync now that finds room; scheduled ticks skip paused schedules, so a new month does not resume them on its own (documented in RB-94; a behaviour change would be its own red task). Gates and tests run once at the S51 end pass (build first, test last).
