---
id: TASK-1472
title: AUD-06 live swap — adopt from empty, newer banner, Open in Excel, source menu, Sign off (A-02-T24)
spec: SPEC-333
acceptance_criteria: [AC-1, AC-4, AC-24, AC-44]
risk_zone: green
status: in-progress
epic: A-02
plan_key: A-02-T24
branch: s12-ledger
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"On staging Simone Baptiste adopts Granite Peak's imported TB and AUD-06 shows it balanced with
total assets 26,410,000 from live routes."

## Plan
- `screens/AUD-06/TrialBalance.tsx`: the empty state offers the entity's snapshots and adopts one
  (`adoptTrialBalance`), the newer banner ("A newer trial balance is available · pulled … · n
  lines changed", *Use vN…* with a reason, `adoptTbVersion`), Open in Excel downloads
  `export.xlsx`, the source menu (*Pull latest*, *Ask client to reconnect*) from
  `allowed_actions` and the engagement's live connection, *Sign off…* opens the
  `signoff:trial_balance:<tb>:L2` overlay target. New pieces lazy-loaded (firm entry at budget).
- Fixture scenarios and tests for `empty` (adopt), `newer` (banner and adopt v2), the source menu
  and export.
- Staging acceptance (Simone, Granite Peak 26,410,000) is a staging step, not run here.

## Progress log
- 2026-10-27: plan written.
- 2026-10-27: built (DEC-612); `TbLive.tsx` lazy-loaded; `Live.test.tsx` covers adopt, newer
  banner, Open in Excel, source menu and Sign off… in fixture mode. Staging acceptance not run here.
- 2026-10-27: vitest AUD-06, AUD-02, C9/C20 fixtures, routes 120 passed; tsc clean for the app
  (12 pre-existing errors in the generated `packages/api-client/src/client/*`, untouched);
  eslint and prettier clean; vite build ok; bundle-budget: firm initial 245.8 of 250 KB, TbLive
  60.7 KB lazy chunk. Playwright not run (chromium mismatch).
