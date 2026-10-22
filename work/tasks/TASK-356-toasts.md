---
id: TASK-356
title: E3 toasts — ToastStore, ToastHost, useToast, running and undoable (F-05-T21)
spec: SPEC-048
acceptance_criteria: [AC-8]
epic: F-05
plan_key: F-05-T21
risk_zone: green
status: done
branch: f05-t21-toasts
created: 2026-10-22
updated: 2026-10-22
---

## Objective
Toasts as the C-21 kit and chapter 04 E3 define them: one store per window, one host at the root,
`toast.undoable` for DEC-24's ten-second window and `toast.running` that settles in place.

## Scope
**In**
- `packages/ui/src/components/toast-store.ts`: `createToastStore` (lib/toast.js semantics: 4 s, 8 s
  with an action, error and running persist, hover pause with at least 600 ms on resume, at most 3
  live, 180 ms leaving), `createToast` (`show`, `undoable`, `running`, legacy `deferred`),
  `duration`, `aria`, `copyProblems`.
- `packages/ui/src/components/toast.tsx`: `Toast` (static specimen), `ToastHost` (`contained`,
  `bottom`, `store`), `useToasts`, the window's `toastStore` and `toast`; `Toaster` is the host's older
  name.
- Specimens: C-21 kinds and a live stack on its own store.

**Out**
- Independent AC tests for overlays, toasts and Undo (F-05-T22).
- Migrating screens' hand-drawn toasts (C-21 step 4) beyond keeping `toast.show` and
  `toast.deferred` working: callers keep their calls.

## Acceptance (F-05-T21)
"The Toast artboard matches (4 s, 8 s with an action, at most 3, hover pause) and undoable only
invokes the caller's compensating command."
- Timings, stack and hover: `toast-store.test.ts` "auto-dismiss", "the stack", "hover".
- Undoable: `toast-store.test.ts` "undoable (E2; DEC-24; INV-1)".
- Host roles, action and close, reduced motion: `toast.test.tsx`.

## Decisions
See "Toasts (F-05-T21)" in `packages/ui/src/tokens/DECISIONS.md`.

## Definition of done
- [x] Tests for the acceptance pass (31 new)
- [x] Type check, lint and format pass
- [x] `make check-fast` passes

## Progress log
- 2026-10-22: built and merged; existing `toast.show` and `toast.deferred` callers unchanged.
