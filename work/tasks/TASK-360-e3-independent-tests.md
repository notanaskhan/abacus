---
id: TASK-360
title: Independent AC tests for E3 overlays, toasts and Undo (F-05-T22)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T22
branch: f05-t22-e3-tests
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Tests prove Escape order, focus trap and return, a peek drawer without a trap, the dirty guard, the
?ov= round trip, and that no gate write is optimistic (INV-1)." Written from F-05 §3.E (E1, E2)
and plan 04 E3, not from the T20 and T21 code (ADR-078).

## Scope
- `apps/web/e2e/e3.spec.ts` (gallery, real browser focus): Escape order with focus return, focus
  trap in a modal dialog and a modal drawer, the peek without trap or focus move, never two
  drawers, the dirty guard on scrim and Escape. Runs in CI's gallery job.
- `apps/web/src/app-core/e3-acceptance.test.ts`: the ?ov= round trip (reload, Back, escaped ids,
  drawer plus modal, one drawer at most, unknown keys).
- `packages/ui/src/components/e3-acceptance.test.ts`: E2 timings and INV-1 (no fetch or XHR from
  the toast store; a deferred gate commit waits out the window and an undone one is never written;
  Undo goes once the effect starts).

## Findings
None: every E1 and E2 statement held. Two notes for the harness: a layer under a modal is hidden
from the accessibility tree (look it up with `includeHidden`), and the gallery holds static
specimen copies of some layers, so live layers are those outside `section[id]`.

## Definition of done
- [x] 6 Playwright, 7 + 7 Vitest checks pass
- [x] `make check-fast`
