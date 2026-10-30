---
id: SPEC-316
title: "Account mapping and draft statements, first slice: firm FS groupings imported and published; the trial balance mapped by account ranges and people's edits; draft balance sheet and income statement by code"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-050, ADR-004, ADR-005]
related_specs: [SPEC-309, SPEC-311, SPEC-313]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
This is the core of A-03's taxonomy and mapping, plus the first AUD-20 view.

- A firm's FS groupings are content: imported as CSV through an endpoint into a draft with its problems listed, never seeded, then published once by a person.
- A trial balance is mapped on a published version. Each account maps by a person's newest edit, or else by the version's account ranges (first rule wins, numeric codes compared as numbers). Rule mappings are computed on read, so a new trial balance version maps without writing anything.
- The mapping is a reviewable. Its content hash covers the version and every account's FS line, so a change makes sign-offs stale.
- The draft statements are built by code.

Migration 0079 adds:
- `grouping_sets` and `grouping_set_versions`; the status and publication columns are the only updatable ones, and a trigger freezes a published version;
- `groupings`, `fs_lines` and `fs_line_range_rules`, all insert-only;
- `mapping_sets`, insert-only, one per trial balance of record;
- `mapping_set_edits`, insert-only, human only; the newest per account counts.

## 2. Acceptance criteria
- **AC-1 Import.**
  - `POST /v1/grouping-sets/imports` (`grouping_set.import`: firm admin, practice leader, quality partner) takes `{key, name, csv}` with the columns `grouping_key, grouping_label, class, fs_line_key, fs_line_label, normal_balance, account_from, account_to`.
  - It creates the next draft version with its problems by row and code: `header`, `missing_key`, `class_invalid`, `normal_balance_invalid`, `duplicate_key`, `range_invalid`, `overlapping_range`, `too_many_rows`.
  - Rows are written only when there are no problems.
  - `GET /v1/grouping-sets` lists versions newest first.
- **AC-2 Publish.** `POST /v1/grouping-sets/versions/{id}/publish` (`grouping_set.publish`: practice leader or quality partner, fresh MFA) publishes a draft with no problems, human only. A published version can't change (409, and the trigger).
- **AC-3 Map.**
  - `POST /v1/engagements/{id}/trial-balances/{tb}/mapping` (`mapping_set.edit`: EP, manager, senior; the agent is denied) starts the mapping on a published version, one per trial balance.
  - `GET …/mapping` returns each account of the current version with EOY, Final and BOY, its FS line, and how it was mapped (edited, by account range, or unmapped). It also returns the groupings with their FS lines, the tallies and the content hash. Before the mapping starts, it returns the published versions to choose from.
- **AC-4 Edit.** `PUT …/mapping/accounts` maps up to 500 accounts to FS lines of the set's version, or back to the rules.
- **AC-5 Sign-off.**
  - `POST …/mapping/sign-offs/prepare|review` records sign-offs on the content hash, refused while any account is unmapped (`unmapped_accounts`).
  - Mapping sets join the sign-off matrix and G5 ("MAP <period end>").
- **AC-6 Statements.** `GET …/statements?layer=unadjusted|final` returns `null` before mapping. Otherwise it returns:
  - groupings with their FS lines: each account's net presented on the line's normal side, current year (Final when chosen and available) and prior year;
  - class totals and net income (revenue − expenses);
  - the balance check: assets = liabilities + equity + net income (pre-closing). It returns the difference, and counts unmapped accounts.
- **AC-7 Web.**
  - Settings › FS groupings: versions with problems, Publish, and Import (CSV file or paste).
  - The trial balance's "Mapping" view: choose the groupings, a per-account FS line picker, the "Unmapped only" filter, tallies, and sign as preparer or reviewer.
  - The "Statements" view: balance sheet and income statement for current and prior year, the balance pill, and an unmapped warning. It follows the Unadjusted/Final toggle.

- **AC-8 Prior-year match and tallies (A-03-T08; TASK-5009).**
  - An account is mapped by a person's edit first. Next comes the line it sat on in the engagement this one rolled forward from (`prior_engagement_id`). That match uses the normalised account code and the FS-line key, so it survives a new grouping-set version. Last come the number ranges.
  - The mapping shows tallies: from prior year, by range, edited, unmapped. It also shows whether the trial balance balances.
  - The preparer's sign-off, refused while any account is unmapped, records `mapping_set.confirmed`.
  - Only line keys cross from the prior year, never its figures.

- **AC-9 Staleness on a new trial balance version (A-03-T14; TASK-5010).**
  - When `trial_balance.version_created` brings version 2 or later and the mapping's newest sign-offs were on other content, assurance emits `mapping_set.went_stale` once per version. The audit records the version and the unmapped count.
  - Review's stale detector then tells each signer (`sign_off.went_stale`, notification `sign_off_stale`).
  - Human edits persist by account code, and new accounts read unmapped.
  - Version 1, a trial balance with no mapping, and an unsigned mapping announce nothing.

## 3. Out of scope
- XLSX import.
- Prior-year mapping match.
- The agent's suggestions (A-09).
- Mapping on a newer trial balance version keeping its own record of edited accounts that no longer exist.
- Disclosure checklist, statement notes, export and tie-out of statements to a client-provided FS (A-10).
- Grouping by FS line on the AUD-06 accounts view.
