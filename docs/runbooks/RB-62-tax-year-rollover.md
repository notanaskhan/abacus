---
id: RB-62
title: "Tax-year rollover (TY2027): reference-set drafts, CPA and counsel review, two-person publish, organizers, the Dec 7 entitlement flip and rollback"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-11-26
---
# RB-62 · Tax-year rollover

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (a late publish) to SEV2 (a wrong due date published) |
| Linked from | none yet |
| SLO affected | none |
| Kill switches that apply | withdraw a reference-set version (`refdata withdraw`, two people); the firm's `tax_returns` entitlement (the `tax.extensions_estimates` flag retired, DEC-2605) |
| Rehearse by | Fri Nov 26, 2027 (staging, PF-X1) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

The plan names this "RB-31's tax-year rollover section"; RB-31 is P-01-T17's notification pause
(runbooks README), so the rollover is its own runbook. Reference content (due dates, holidays,
8879 sets, thresholds) lives in reference-set versions in the database, never in a commit
(DEC-76); the one repo file is a module's parameter file.

## 1. Draft (by Fri Nov 19, 2027)

For each set the season needs, write a draft **outside the repository** (the tool refuses inside):

```
python -m abacus_tools.refdata_rollover --kind due_date_rules --key <TY2026 key> --to-year 2027 --out <ops folder>
python -m abacus_tools.refdata_rollover --kind form_8879_set --key <TY2026 key> --to-year 2027 --out <ops folder>
python -m abacus_tools.refdata_rollover --kind information_return_thresholds --key <PY2026 key> --to-year 2027 --out <ops folder>
python -m abacus_tools.refdata_rollover --kind legal_holidays --to-year 2028 --out <ops folder>
```

Each draft carries a `review` block: what a person checks before it becomes a version. Rolled sets
move their year and carry everything else over; the 8879 tolerances are carried **for
re-verification**, never defaulted (DEC-85). Holidays are computed from 5 U.S.C. 6103 and D.C. Code
§ 1-612.02 at their observed dates (DC Emancipation Day 2028 is observed Mon Apr 17, so TY2027
Forms 1040 are due Tue Apr 18, 2028).

**Pilot-state due dates** are not a kind yet: `Jurisdiction` is `US` or `DC` (C21). A state's rules
need the kind extended before they can be drafted; until then the state column in the workbook
review records "not modelled" and each firm's state deadlines stay in its own calendar.

## 2. Review (by Fri Dec 3, 2027)

- The tax CPA reviews every draft against the IRS sources named in its `review` block and records
  each check in `docs/quality/golden-reviews/ty2027-reference-sets@1.md`.
- Counsel reviews the 8879 set and the Pub 1345 tolerances (DEC-85) and signs the same memo.
- A changed row goes back to step 1 with the change, never edited in the database.

## 3. Publish (staging, then production by Tue Dec 7, 2027)

1. Remove the `review` block from the reviewed file (the CLI refuses unknown keys).
2. `make refdata-draft ARGS="--key us-federal-due-dates-ty2027 --kind due_date_rules --tax-year 2027 --effective-from 2027-01-01 --file <reviewed file> --drafted-by <handle> --reason 'TY2027 rollover, reviewed <memo>' ..."`
3. `make refdata-diff ARGS="--key ... --file <reviewed file>"`: every changed row read by both people.
4. The **other** person publishes: `make refdata-publish ARGS="--version <uuid> --approver <handle> --reason '...'"` (the database refuses the drafter).
5. Staging first, checked on PF-X1 (TAX-13 resolves TY2027 due dates from the published rows,
   each carrying both handles); then production the same way, as the `ops-task.yml` one-off task.

Never beside a hosted deploy: with the deploy lock held the CLI refuses (`ABACUS_DEPLOY_LOCK_ENV`).

## 4. Organizers (by Fri Dec 10, 2027)

Each pilot firm's owner publishes its TY2027 organizer from BND-03 (firm content, the firm's own
act). The dossier records the date. There are no live pilot firms (DEC-1391); PF-X1 rehearses it.

## 5. The flip and its rollback (Tue Dec 7, 2027, 19:00 CT)

- The firm's `tax_returns` entitlement on, both founders approving in the dossier. The
  `tax.extensions_estimates` flag retired into it (DEC-2605, merged 2026-11-08), so there is no
  flag to flip.
- **Rollback:** the firm's `tax_returns` entitlement off; a wrong published row is withdrawn
  (`refdata withdraw`, two people) and the prior version reads again; a corrected version is drafted
  and published through steps 1 to 3.

## 6. Verify

- TAX-13 on PF-X1 shows TY2027 extended due dates from the published rows.
- `make flag-calendar` clean through the Jan 1 to Apr 20, 2028 window.
- RB-16's R4-16 line ticked with the versions per firm.

## Rehearsal log

| Date | Where | Who | Result |
|---|---|---|---|
