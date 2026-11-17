---
id: TASK-8531
title: "A-08-T32: Live swap prerequisites: independence-import lint ban (partial)"
spec: SPEC-657
acceptance_criteria: []
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
