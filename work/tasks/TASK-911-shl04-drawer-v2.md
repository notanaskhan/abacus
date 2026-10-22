---
id: TASK-911
title: SHL-04 drawer v2 - O2 frame, segmented tabs with counts, day groups (P-01-T10, part 1)
spec: SPEC-013
acceptance_criteria: [AC-4, AC-7]
risk_zone: green
status: in-progress
epic: P-01
plan_key: P-01-T10
branch: TASK-911-shl04-drawer-v2
created: 2026-10-23
updated: 2026-10-23
---

## Objective
The bell opens the notifications drawer v2 as the `?ov=notifications` layer. It is an O2 peek, 480
wide and without a scrim, and it has:

- the header "Notifications" with Mark all read;
- a Segmented track whose counts come from the C16 v2 feed;
- the rows grouped by day on the firm's calendar ("Today", "Friday, September 11");
- unread rows drawn as weight 500, a 7 px brick dot and a hidden "Unread";
- EmptyState and Skeleton states, and the footer "Showing 30 days".

Opening the drawer marks nothing read. Opening a row marks it read and deep-links. Scenarios a, b,
b′, b_raj and c–g each have a test.

## What changed
- **Drawer** `apps/web/src/shell/firm/NotificationsDrawer.tsx`: the drawer itself, `groupByDay`,
  `tabOptions`, `rowButton` (a deep link only; no Approve/Sign off/Release/Send/Post/Decide on
  an agent row) and the `notifications` overlay registration. Agent rows' context goes through
  AgentText. Copy is in `shell/firm/copy.ts` (`NOTIFICATIONS`).
- **Helpers** `apps/web/src/shell/notifications.ts`:
  - `firmDayGroup(iso, now, tz)`. SPEC-305's `dayGroup(iso, now)` buckets ("Yesterday",
    "Earlier this week", "Older") do not give the handoff's "Friday, September 11", and its test
    pins them, so the v2 drawer uses this tz-aware sibling. `now` comes from `app-core/clock`'s
    `useNow`.
  - `kindGlyph` and `feedHref` (the legacy engagement page while the designed targets are
    planned).
- **Layout** `legacy/Layout.tsx`: the bell and SHL-03's Notification preferences row open and
  close `?ov=notifications` through `useOverlays`. The v1 `NotificationDrawer` is no longer
  mounted; its file and test stay until the v1 feed retires.
- **packages/ui** `format.ts`: `weekdayDate` ("Friday, September 11", with the year outside the
  current one) and `sameDay`, with tests.
- **Fixtures** `fixtures/scenarios/SHL-04.ts`: read and read-all handlers that later pages read
  back, and v1 `GET /v1/notifications` for the bell's `unread_count`.
- **Screen** `apps/web/src/screens/SHL-04/` (artboard, the scenarios re-export without
  `settings`, 17 tests), and the gallery at `/components/screens/SHL-04?st=`. The manifest stays
  `planned`; see Deviations in `docs/screens/SHL-04.md`.
- **Docs** `docs/screens/SHL-04.md`.

## Not in this part (P-01-T10 remains open)
- Inline Accept and Return… on row d, which also needs the Return reason dialog.
- The receipt's 10 s Undo. It needs P-01-T13's undo route, which is not in the generated client
  yet. Frame c shows the receipt from `facts.receipt`.
- The Notification settings menu with `GET`/`PUT /v1/me/notification-preferences`. The scenario
  data exists.
- The manifest move to `fixture`, together with the SHL-04 → SHL-03 link (link-contract rule 1).

## Commands
```
pnpm -C apps/web exec tsc --noEmit   # 0 errors in src; 12 pre-existing in packages/api-client/*.gen.ts
pnpm -C apps/web exec eslint src/shell src/screens src/fixtures src/legacy/Layout.tsx src/routes/manifest
pnpm -C apps/web exec vitest run src/screens src/routes src/gallery src/legacy src/shell src/fixtures src/app-core
pnpm -C packages/ui exec vitest run src/format.test.ts
make check-generated
```

## Progress log
- `2026-10-23`: Built part 1 as above. All checks above passed.
  - Skipped Tier C parity and axe. P-01-T16 locks both (epic §5.4).
  - Deferred the items listed under "Not in this part".
