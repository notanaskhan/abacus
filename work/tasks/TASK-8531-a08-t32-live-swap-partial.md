---
id: TASK-8531
title: "A-08-T32: Live swap prerequisites: independence-import lint ban (partial)"
spec: SPEC-657
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
branch: a08-t32-lint
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T32
---

## Objective
Fixture-to-live swap on staging for the five screens and the AUD-11 MUS option; manifest links planned to live; lint rule keeps the independence MyConfirmations screen untouched. AC: all five screens run live on staging and no import of the independence confirmation code exists in domain/audits.

## Plan (green)
1. eslint.config.js: importRestrictions takes extra patterns; src/domain/audits/** bans MyConfirmations and *Independence* imports (A-08 §5.2)
2. Probe: a domain/audits file importing MyConfirmations fails lint; domain/audits passes today
3. Remainder (staging): the five screens' live hosts on the generated client, manifest links planned to live, the AUD-11 MUS option

## Progress log
- `2026-11-17` — Partial: the lint half is built and probed. The staging half (live hosts for AUD-12/13/14/26 and POR-17 against the scenario, manifest links to live) waits on staging; AUD-12 and POR-17 already have live hosts from S47/S48. Gates and tests run once at the S49 end pass (build first, test last).
- `2026-11-18` — Staging half looked at (S49 open rows): not a swap. AUD-13, AUD-14 and AUD-26 were built on the seed constants (`screens/kit-a08-data.ts`, `fixtures/seed/fieldwork.ts`), not on the generated client, and the API shapes do not carry what the artboards draw: `ConfirmationRowOut` has no item description, address text, confirmed or difference amount (AUD-14's log columns); `AnalyticsSetOut` carries the lines but not the explanations, adjustments and subtotals AUD-13 reads from seed maps (they sit behind the explanations routes); `SsarsWorkspaceOut` carries the rail but AUD-26's canvases read the seed. Each live host needs the screen re-plumbed onto its reads, and AUD-14 a contract change first (contract-first rule), before any staging run. Left open; AUD-11 MUS option likewise open.
