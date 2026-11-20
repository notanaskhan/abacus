---
id: TASK-8823
title: "Q-05-T17: Reissue and intake"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q05t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T17
---

## Objective
Choosing Revise and reissue on PI-01 makes AUD-23 g live with a dual date, and filing the Harborline PDF from INB-01 creates the PI-01 source with no other write to the locked work item.

## Done
- assurance/post_issuance_reissue.py: reopen_for_reissue (EP, fresh MFA, a decided revise_and_reissue case: new dual-dated audit_report_versions draft naming the original release, the report's current version moved, under post_issuance), record_notify_users (manual step, audited only), INB-01 destination post_issuance_source (open cases of the client; files the document as the case's source in post_issuance_sources, nothing else)
- A-07 release: kind reissue + reissue_of_id when the released version is a reissue draft; request_release no longer replays the original for a reissue
- communications IntakeDestination.after_file hook
- migration 0997 post_issuance_sources; route reopen-for-reissue wired
- tests

## Progress log
- `2026-11-20` — Plan (red): service, release tweak, intake hook, migration; rollback revert + downgrade 0997. The analysis route stays 501 until the capability (after its eval suite).
