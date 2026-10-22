---
id: TASK-902
title: CLOCK-001 banned pattern and the ESLint clock ban (F-04-T17)
spec: SPEC-307
acceptance_criteria: [AC-7]
risk_zone: red
status: done
epic: F-04
plan_key: F-04-T17
branch: f04-t17-clock-lint
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Both rules fail on a new `now()` outside `kernel/clock.py` or `clock.tsx`; `main` stays green."

## What changed
- **CLOCK-001** in `banned_patterns`:
  - flags `datetime.now`, `datetime.utcnow`, `datetime.today`, `date.today` and `time.time` anywhere under `src/`;
  - exempts `kernel/clock.py`, plus `kernel/config.py`, which `kernel.clock` imports;
  - tests are outside the rule.
- **The frontend half** (`packages/ui/eslint-design-rules.js`):
  - `CLOCK_SYNTAX` bans an argument-less `new Date()` alongside the existing `Date.now` ban;
  - both apps exempt their `clock.tsx` files.
- **Fixed:** the one violation it found, `dayGroup` in `shell/notifications.ts`, which defaulted `now` to the wall clock. Every caller already passes it.
- **Tests:** unit tests for CLOCK-001 (flags, exemptions, the clock API), and ESLint tests in `src/lint/eslint-rules.test.ts`.

## Progress log
- 2026-10-23: banned_patterns is clean on main, ESLint is clean in apps/web and packages/ui, and the new tests pass.
