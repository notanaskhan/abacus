---
id: TASK-1441
title: "Fixture-mode Playwright specs for SHL-07 and SHL-08 with axe, Tier D, keyboard and reduced motion (P-03-T24)"
spec: SPEC-322
acceptance_criteria: [AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22]
risk_zone: green
status: in-review
epic: P-03
plan_key: P-03-T24
branch: s11-trust-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s11-trust-tests (S11 lane 7; a clean session following .claude/skills/ac-test-author/SKILL.md, from the spec, contracts and ADRs only)
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Both specs pass in fixture mode with axe clean, Tier D assertions blocking, and SHL-07a/b/e and
SHL-08a/b/c/d/e locked at Tier C."

## Plan
- `apps/web/e2e/trust/shl-07-citation-popover.spec.ts` and `shl-08-source-viewer.spec.ts`, from
  the /components gallery on fixtures (chromium project, `ABACUS_VISUAL=1`).
- Run locally once with an untracked config pointing at the cached chromium (deleted, never
  committed). Rollback: delete the two files.

## Results
- SHL-07 (20 run: 18 pass, 2 expected failures): axe AA per artboard; Tier D 372/420 wide, radius
  12; reduced motion; Enter pins a named non-modal dialog and Escape returns focus to the cell; the
  hover preview never takes focus; Re-link by keyboard; stepper named. **Expected failures
  (`test.fail`, ED-166):** the pinned popover does not take focus, and "Source 2 of 3" is an
  aria-label on the counter, not announced.
- SHL-08 (32 pass): axe AA per artboard; toolbar buttons 26 px, all named, no Download; reduced
  motion; drawer 480 with a 46 px header and 14.5/500 title, labelled; dock 330; linked-figure rows
  36 px; toolbar by keyboard; the unlock form labelled, keyboard-submitted, cleared, error tied by
  `aria-describedby`, axe clean after the error; Reveal reachable with a polite live region.

## Out of scope
- Tier C parity locking of SHL-07a/b/e and SHL-08a–e is the parity harness and a human sign-off.

## Progress log
- 2026-10-27: specs written and run locally on the cached chromium-headless-shell 1248 (Playwright
  1.63 pinned): 50 pass, 2 expected failures. Local config deleted.
