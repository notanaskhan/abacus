---
id: TASK-6740
title: "S35 round 2 end pass: gates, tests, security review and re-review, main reds, A-07 wiring found by the archive load"
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-07
branch: s35b-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: S35-end-pass-2
---

## Objective
The round-2 rows (A-07-T41, A-07-T43, A-07-T47, Q-03-T235, Q-04-T136) pass the gates and their
tests. The S35 batch's main reds (CI 42922051674 on #1667) are fixed or recorded.

## What the end pass found and fixed
- **Gates.** These failed and are fixed:
  - pyright errors in the new tests, and a type-checker ignore with no reason;
  - `error-codes.yaml` out of date (it also gains main's missing `filing_evidence_required`);
  - task-file spec fields, and an SSN-shaped test value;
  - the AUD-06 route budget: the live hooks now load lazily from `domain/completion-live`.
- **Security review.** One finding, fixed: the report date could change after the EP's L4
  approval (the date is outside the version's hash). The one re-review of the fix round found
  nothing new.
- **The archive load, first run of these A-07 paths against Postgres.** Each was a hard failure:
  - the EQR checklist provider was never registered;
  - the EQR resource had no work item, so `function_in: eqr` failed closed;
  - EQR notes had no reviewable facts, and the matrix gave `eqr_reviewer` no right to raise or
    clear them;
  - report versions had no sign-off facts, and approval needs the preparer's L1 first;
  - migration 0802 grants the `agent_run_steps` insert columns a code run writes and
    `audit_reports.template_id`;
  - `published_clauses`'s untyped `:name` parameter;
  - text in `Ref` (an EQR checklist update, the rep letter's send and signature, a failed
    release);
  - a code run failing with a NULL failure code;
  - `loader.load` taking `audit_core` twice, and duplicate A-07 checklist event labels;
  - the fixture export's identity lookup pointing at the developer's database.
- **Main reds from S35.**
  - Masking on the TIN-bearing workbook stub routes.
  - The `seal_verify` schedule and `todo_assigned`'s email default in their tests.
  - The workbook stub's untyped statuses, recorded as F-03 findings.
  - Two acceptance tests that compared dates in UTC.
  - Gallery axe: the DRAFT watermark is drawn by CSS (it failed contrast as text). The
    scrolling panes are focusable. The Locked icon now has a role.
  - Modal layers carry `aria-modal`; the inline O3 sheets trap focus and return it to their
    opener.
  - AUD-22 and AUD-23 now lay out 470 · 896.
  - The portal brand check now matches the product name only, not "Accrued expenses".
- **Findings recorded, as strict expected failures that flip when fixed:**
  - representations 12 and 15 are off: no slice seeds late remittances or related parties;
  - the binder's A–E counts differ from the design;
  - AUD-22 a2's send sheet is not built;
  - the A-07 T2 artboards draw no rail;
  - the ask card has no radiogroup since P-09-T14.

## Not done here (flagged)
- **Release, lock and the addition run only with a worker.** Load to Dec 3 or Jan 15 with
  `make dev` and `make seed-demo SLICE=archive`.
- **Granite Peak's release** waits on its governance body seed.
- **The 10:05 fixture export is not reproducible.** Its also-required values carry the
  database's clock, so the export isn't committed.
- **The gallery suites were not running on main.** They had skipped on main since S34 because of
  the gallery path filter, so every red here was latent before S35 unless noted.

## Progress log
- `2026-11-11` — Gates green; unit green except WeasyPrint (local only); targeted integration
  green (8726 + the A-07 loads); Playwright axe, visual and journey reruns as listed in the PR.
