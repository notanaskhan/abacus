---
id: TASK-8750
title: "F-08-T11: Independent AC tests for the Sheet kit (ADR-078); status words asserted against the kit-local draft types until F-08-T04 lands"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s51-f08t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T11
---

## Objective
Tests prove locked rows refuse every edit path, agent cells never turn ink without a human adopt, and no human-only verb renders on an agent element.

## Plan (amber)
1. Files: `packages/ui/src/sheet/__ac__/fixtures.tsx`, `locks.ac.test.tsx` (test_ac1-6: aria-readonly, Lock 11, exact tooltip; typing, Enter/F2, Delete, Backspace, paste ClipboardEvent, Ctrl/Cmd+D fill, cut; lock from row.locked only, never presence) and `agent-cells.ac.test.tsx` (test_ac1-7: draft SheetCellState words; suggested while onAdopt pends or rejects; no Adopt for agent/system; 'Edited by HL · was Properly included' survives a re-render; no citation marker or count without typed locators even with '[1]' in the value; no approve/sign off/release/send/adopt/accept on agent-owned elements).
2. No migrations, registry or flag edits.
3. Commit the tests first, log the failures, then fix the kit.
4. Rollback: revert the PR.

## Progress log
- `2026-11-20` — Solo deviation from ADR-078: no separate author (AMENDMENT-solo); tests written from F-08 §3 A2-A3 and types.ts before changing the kit, though this session built T06/T07. Failures before the build: (1) locks test_ac5: cut on a locked row was not refused (no onCut, defaultPrevented false); (2) agent-cells test_ac6: the tooltip read '0 citations' with no typed locators; (3) agent-cells test_ac7: the test's run snapshot was not stable (useSyncExternalStore loop), fixed in the test fixture, not the assertion. Build: SheetGrid refuses cut like paste with the lock copy; suggestionLines drops the citation count when there are none. 13 AC tests pass; sheet, attribution and sheet-layout 56 pass; tsc and eslint clean. Gates and tests run once at the S51 end pass (build first, test last).
