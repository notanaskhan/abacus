---
id: TASK-1220
title: POR-03 frontend part 2 — b, motion, c from drop polling, c2, d, i, M, the portal mount (R-01-T10)
spec: SPEC-323
acceptance_criteria: [AC-1, AC-5]
risk_zone: green
status: done
epic: R-01
plan_key: R-01-T10
branch: s8b-portal-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"All twelve POR-03 states render from fixtures and, full stack on staging, Claire's three-file drop reproduces c and d with the outcome announced in a live region."

## What was built
- `screens/POR-03/index.tsx`: the drop view (motion beats with the reduced-motion and `?static=1` still frame; `useDropBatch` polling; the live region; refusals under the drop zone), the audit variant (kit `bands`, the other-parties note, the band rail), T7-M (`RequestMobile`, the accept list, Mark as Done in the sticky footer), `onNavigate`.
- `domain/portal/drops.ts` (`useDropBatch`, `dropOutcome`); `documents.ts` `send` answers the server's batch id and the refused files; `messages.ts` the sorted and refusal words, `due`.
- `packages/ui/src/requests`: `reveal`, `bands` (BandSection, BandRow), `note`, `accept`, `drag.badge`, `MarkAsDone wide`, `RequestItem.due`.
- `routes/portal/index.tsx`: `/documents` mounts POR-03 (`?binder=`, 390 below 768 px); POR-02's POR-03 to-do link, "Open binder" and the toolbar route through `AREA_PATHS`.
- Fixtures: Dana's census row carries its Sep 2 upload.

## Progress log
- 2026-10-25: built; `vitest run src/screens/POR-03` 25 passed (11 new: the twelve states, b, motion, static, c polling, c2, d, i, M, a live three-file drop, a refusal); POR-02 navigation tests 2 new. DEC-347 recorded. **Not done here:** the staging run of the acceptance (full stack on staging is the main session's or R-01-T31's); per-band icons and the motion frame's upload sizes (parity masks, R-01-T31); the manifest entry stays `planned` (DEC-347).
