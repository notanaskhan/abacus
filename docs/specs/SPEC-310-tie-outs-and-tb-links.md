---
id: SPEC-310
title: "Tie-out checks on the trial balance (balanced, tie, rollforward) and working-paper cells linked to the trial balance with TB()"
status: approved
owner: founder
risk_zone: amber
related_adrs: [ADR-004, ADR-050, ADR-005]
related_specs: [SPEC-308, SPEC-309]
created: 2026-10-21
updated: 2026-10-21
---

## 1. Summary
This builds A-02's ties (§3.3; T11 and T17) and the first link from working papers to the trial balance of record.

- People define checks on a trial balance. The tie engine (`workpapers/ties.py`, exact `Decimal`) computes each result on read from the current version. Nothing is stored.
- Working-paper formulas gain `TB()`. A paper that uses it records the trial balance version in its content hash, so a new version shows its sign-offs as stale.

Migration 0074 adds:
- `tie_out_checks` (only `current_version_no` is updatable);
- `tie_out_check_versions` (insert-only). Database CHECKs refuse an uncited expected value and a non-human author.

## 2. Acceptance criteria
- **AC-1 Results.**
  - `GET /v1/engagements/{id}/trial-balances/{tb}/checks` returns each check with its status:
    - `tie` when within tolerance;
    - `off`, with the difference (actual minus expected);
    - `pending` when the trial balance can't answer (a missing account, or no prior year for a beginning-of-year check).
  - The kinds are:
    - `balanced`: debits against credits for a column;
    - `tie`: the selected accounts' net, optionally negated for credit balances, against an expected value;
    - `rollforward`: against signed components, with the arithmetic as text ("288,500.00 + 96,200.00 − 57,450.00 − 14,850.00 = 312,400.00").
- **AC-2 Define.**
  - `POST …/checks` creates a check. The key is derived from the label.
  - Shapes are checked per kind.
  - An expected value without an evidence citation gives `citation_required`.
  - Citations must belong to the engagement.
  - The agent is denied `tie_out_check.define`.
- **AC-3 Edit.** `PUT …/checks/{check}` writes a new version with a reason and `seen_version`. A stale version gives `tie_out_check_stale`. The kind can't change.
- **AC-4 TB() in working papers.**
  - What a cell can read:
    - `=TB("1000")` reads an account's end-of-year net on the engagement's Standard trial balance (the one with the latest period end);
    - `TB("1000","BOY")` reads the beginning of year;
    - `TB("1000:1099")` sums a range of codes.
  - A missing trial balance or account gives `#TB!`.
  - Such cells are stored with value_source `tb_linked`.
  - The working paper shows which trial balance it reads, and the accounts whose WP ref is the paper's code. Clicking one links the selected cell.
- **AC-5 Web.**
  - A check strip on the trial balance shows tie, off n or Pending pills, with the arithmetic in the tooltip.
  - "Add check" opens a sheet with the kind, accounts (prefilled from the selection), column, credit-balance toggle, expected value or rollforward lines, and a required source.

## 3. Out of scope
- Linking a check to an issue (C3).
- Editing checks from the UI (the API exists).
- A check reaching P-04's stale consumer for trial balance sign-offs.
