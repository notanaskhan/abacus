---
id: TASK-378
title: Rename reminders to follow-ups - tables, routes and identifiers (F-03-T16)
spec: SPEC-027
acceptance_criteria: [AC-9]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T16
branch: f03-t16-follow-ups
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"No table, route or Python identifier named reminder remains outside UI copy, and the
follow_up.draft and follow_up.send actions are unchanged." (DEC-74 rename only)

## Plan (red)
- Migration 0087: `reminders` → `follow_up_schedules`, `reminder_items` → `follow_up_items`,
  `reminder_id` → `follow_up_id`, the index; grants, policies and constraints follow.
- Routes `/v1/engagements/{id}/reminders…` → `…/follow-ups…` (actions unchanged); generated client
  regenerated; web screen `FollowUpDrafts`.
- Modules `agents/follow_ups.py`, `communications/follow_ups.py`; identifiers renamed
  (`FollowUpSchedule`, `FollowUpItem`, `send_follow_up`, `chase_overdue`, …). An AST scan of
  `src/` finds no identifier containing "remind".
- L12: the three legacy allowances for the old names are removed, so the glossary's ban now holds
  everywhere (its test updated to say so).
- Kept on purpose: stored values (`reminders.drafted` event type and notification kind,
  `reminder.drafted` audit action, `reminder` audit target, agent activity codes), so past rows
  still read; renaming those needs a data migration of its own.
- Rollback: revert, downgrade 0087.

## Definition of done
- [x] Agents, communications, API, quality and back-fill suites; schema check; web tests
- [x] `make check-fast`

## Progress log
- 2026-10-22: built in one session.
