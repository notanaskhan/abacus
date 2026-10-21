---
id: TASK-325
title: "F-05-T10: format.ts with bigint decimals, Amount, DateText, ClockProvider and useNow"
spec: SPEC-048
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
branch: task-323-format-clock
worktree: agent-af45964d0d63a0cb2
created: 2026-10-21
updated: 2026-10-21
---

## Plan
- **Plan source:** `docs/plan/04-frontend-architecture.md` section 3.7, epic F-05 section 3.B (B1). The
  handoff's `specs/05-data-formatting.md` and `reference/formatters.ts` give the strings; where they
  differ the plan wins (see DECISIONS.md).
- **`packages/ui/src/format.ts`** (the only formatter; no React):
  - money and decimals parse exactly into a scaled `bigint`, never through `Number` or `parseFloat`;
  - `amount(v, 'whole'|'money'|'cents', {zero})` returns `{text, tone}`: half away from zero, negatives
    in parentheses, zero (after rounding) an em dash unless `zero: 'explicit'`;
  - `prose`, `count`, `pct`, `ratio`, `progress`, `bytes`;
  - `date`, `dateTime`, `time`, `relative`, `since`, `period`, `longDate`, `monthYear`, `isoDate`, in
    the firm's zone (default America/Chicago), counting days on the firm's calendar so Yesterday and
    the Nov 1 2026 DST change hold; zone labels come from Intl `shortGeneric`;
  - `accountMask`, `ssnMask`, `einMask` take the last four digits only and throw otherwise (ADR-031);
    `cellRef`, `viaAgent`, `SEP`, `DASH`.
- **`packages/ui/src/clock.tsx`:** `ClockProvider` takes a now-source function and a zone as props;
  `useNow`, `useToday`, `useTimeZone` and `useFormat` (the date formatters with now and zone bound).
  With no provider the device clock and the default zone stand in.
- **`packages/ui/src/components/amount.tsx`:** `Amount` (colour from the tone, tabular figures) and
  `DateText` (a `<time>` element). Exported from `@abacus/ui` with the format functions.
- **`apps/web`:** `routes/root.tsx` gives the root route a component that wraps the outlet in
  `<ClockProvider now={nowMs}>`. `app-core/clock.tsx` is untouched: its resolution order stays.
  Every `toLocale*`, `Intl` and `toFixed` call site moved to `format.ts`; `LEGACY_FORMATTING` is gone.
  `screens/amounts.ts` delegates to `format.ts` and keeps its exports.
- **`packages/ui` gets a test runner** (vitest, jsdom, testing-library, all on the allowlist already);
  `make ci-frontend` runs it before the web tests.
- No migration, no backend change. Rollback is a revert.

## Notes
- The plan wrote `<Amount value style/>`; `style` here is the number format, so `Amount` does not
  accept a CSS `style` prop.
- `since` and `progress` are not described beyond their names in the plan. `since` is "Just Now",
  "5 Min Ago", "3 Hr Ago" (same day), then the list-relative form. `progress` is "17% (4 / 24)", the
  handoff's `formatRatio`. `ratio` is the fixed-decimal score ("0.85") the gallery needed.
- A malformed money or date value throws a RangeError instead of printing: a wrong number must fail
  loudly.
- Left alone, on purpose: the four `Date.now()` files in `LEGACY_CLOCK` (token lifetime and elapsed
  polling windows, not business time), and `dayGroup` in `shell/notifications.ts` (a day grouping on
  the device's calendar; its test passes naive local times). The drawer now passes it `useNow()`.
- Planning keeps whole-dollar materiality ("$252,200"), and the trial balance keeps zero as `0.00`
  through `amounts.ts`; both are the screens' existing, tested choices.
- The independent golden suite is F-05-T11, written separately. These tests are only for this task's
  own rules.

## Definition of done
- [x] `pnpm -C packages/ui test` passes (format and clock tests, including the golden examples,
      DST and Yesterday across midnight).
- [x] `pnpm -C apps/web test` passes (the Board queued-time test now expects the firm-zone time).
- [x] Lint and typecheck pass in `apps/web` and `packages/ui`.
- [x] No `toLocale*`, `Intl` or `toFixed` outside `format.ts` in `apps/web/src` and `packages/ui/src`
      (the one tests file for the lint rules aside).

## Progress log
- `2026-10-21` — format.ts, clock.tsx, Amount and DateText built with tests; 46 call sites moved;
  `LEGACY_FORMATTING` removed; ClockProvider wired at the root. Gates run: ui tests, web tests, lint,
  typecheck, prettier.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Plan wins over the handoff's `formatters.ts` (no floats; firm-zone dates) | Plan section 3.7 | no |
| `format.ts` at `packages/ui/src/format.ts`, not `src/lib/` | No `lib/` exists yet; the lint glob is `src/**/format.ts` | no |
