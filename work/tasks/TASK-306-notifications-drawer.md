---
id: TASK-306
title: "Notifications drawer and partner-decision notifications"
spec: SPEC-305
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: amber
status: done
branch: task-306-notifications
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Plan
- `fieldwork/events.py`: three events, emitted from set_materiality, record_risk and set_severity.
- `notifications/catalogue.py`: a `_partners` recipient and three kinds with templates; the catalogue test is updated.
- Web:
  - `shell/NotificationDrawer.tsx`;
  - `notifications.ts`: categoryOf, dayGroup, and the new texts and destinations;
  - Layout mounts the drawer.

## Definition of done
- [x] The notifications, worker and fieldwork unit tests pass, as do `notificationDrawer.test.tsx` and the shell and Layout tests; check-fast passes.

## Progress log
- 2026-10-20: built and merged.
