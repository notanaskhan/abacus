---
id: TASK-1437
title: "Independent AC tests (ADR-078) for the amber viewer UI: reveal and unlock leave no copy (P-03-T23)"
spec: SPEC-322
acceptance_criteria: [AC-26, AC-28, AC-31, AC-34, AC-35]
risk_zone: amber
status: in-review
epic: P-03
plan_key: P-03-T23
branch: s11-trust-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s11-trust-tests (S11 lane 7; a clean session following .claude/skills/ac-test-author/SKILL.md, from the spec, contracts and ADRs only)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"After re-mask or unmount no copy of the revealed value or the password remains in the DOM,
browser storage or React Query cache."

## Plan
- **File:** `apps/web/src/screens/SHL-08/SHL-08.independent.test.tsx` (Vitest), the SHL-08 and
  SHL-07 fixture scenarios through the generated client, with the test's own QueryClient and a
  memory router so the caches, URL and history state can be read.
- No production change. Rollback: delete the file.

## Results (20 tests, all pass)
- MaskedValue: while shown the clear value is in no cache, storage, URL or history entry; after
  Hide, the 30 s window, a route change and unmount it is nowhere (DOM markup and input values,
  query and mutation caches including variables, local and session storage, URL, history state);
  still shown at 29 s.
- Unlock form: `type=password`, `autocomplete=off`; a wrong, a right, an unsent (unmounted) and a
  rate-limited password leave no copy in any of those places; the field clears.
- Agent surfaces: no control inside `data-actor="agent"` text on SHL-08 a, c, d, f; on the dock
  (Agent · Viewer · Notes) human-only controls sit only inside the viewer; SHL-07 a–e popovers
  (agents' citations) offer neither Reveal nor Unlock.

## Not covered
- The dock's Agent pane is not rendered on the SHL-08b artboard (the segmented control is static),
  so the test proves the dock as rendered.

## Progress log
- 2026-10-27: suite written; one fix round (the mask "•••-••-6081" is not the value; a fresh
  unlock scenario per test; the dock as rendered); vitest: 20 passed.
