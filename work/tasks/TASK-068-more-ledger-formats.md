---
id: TASK-068
title: "Ledger file import, part 3: QuickBooks Desktop, NetSuite and Sage Intacct trial balance exports"
spec: SPEC-028
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: amber
status: done
branch: task-068-more-ledger-formats
worktree:
created: 2026-10-14
updated: 2026-10-14
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-028 Q1's follow-up (Act 2 plan A1): firms whose clients use QuickBooks Desktop, NetSuite or Sage Intacct can import a trial balance export too. There's no model and no connector involved, so the data boundary doesn't apply.

## Scope
SPEC-028 AC-1 to AC-6 for three more formats. General ledger detail stays a separate spec (SPEC-028 Q5).

## Context to load
- Spec: `docs/specs/SPEC-028-ledger-file-import.md` (§4, Q1, Q2, Q6); ADR-107
- Code: `connections/import_formats.py` (`Format`, `FORMATS`), `connections/import_parse.py` (`_header_index`, `_period_end`, `_account`, `_mismatch`), `abacus_tools/synthetic/ledger_exports.py`, `apps/web/src/screens/LedgerExport.tsx` and `importMessages.ts`

## Plan
- [x] Plan approved by human (founder, 2026-10-14: D1–D4 as recommended). Approved by founder: the paths named in D4

### What the code shows
- **Formats are configuration.** Each one defines the file type, the header labels for the account, debit and credit columns, where the account code sits, the total-row labels, the period line's prefix, and the guided steps. The parser applies them as plain code.
- **Account codes** are read from a leading number ("1000 Checking") or a trailing parenthesis ("Sales (200)"). A code in its own column isn't supported yet.
- **The period line** is a prefix plus a full date. A month-and-year period ("Dec 2026") isn't read yet.
- **A file that fits another format** is refused as `looks_like_<system>`. The format list and the steps come from the API, so the screen needs no change beyond any new wording.

### Design (for founder review)
1. **Three formats** (D1, D3). The layouts come from each system's documented trial balance export and are checked against synthetic fixtures (TASK-052 D4).

   | Format | File | Account column | Code | Debit / credit | Total | Period line |
   |---|---|---|---|---|---|---|
   | QuickBooks Desktop (`qbd_tb_xlsx`) | Excel | blank header | leading, also "1000 · Checking" (middle dot) | "Debit" / "Credit" | "TOTAL" | "As of December 31, 2026" |
   | NetSuite (`netsuite_tb_csv`) | CSV | "Account" | leading ("1000 Checking", or "1000 - Checking") | "Debit" / "Credit", or "Amount (Debit)" / "Amount (Credit)" | "Total" | "End of Dec 2026", "As of Dec 2026" or a full date (D2) |
   | Sage Intacct (`intacct_tb_csv`) | CSV | "Account title", with the code in "Account no." | its own column | "Debit" / "Credit" | "Total" | "As of 12/31/2026" |

2. **Parser additions** (pure, in `import_parse.py`):
   - a code style `column`, where the account code is read from its own header (`code_header`);
   - " · " and " - " accepted between a leading code and its name;
   - month-and-year periods read as the last day of that month (D2);
   - US numeric dates (12/31/2026).
   - The existing checks (balanced, the period matches the year end, USD, control totals from the total row or the lines) apply unchanged.
3. **Telling formats apart:** each format's header and code style must not fit another's, so `looks_like_<system>` stays exact. There is a unit test per pair.
4. **Guided steps**, from each system's menus:
   - **QuickBooks Desktop:** Reports, then Accountant & Taxes, then Trial Balance; set the date; Excel, then Create New Worksheet; save as .xlsx.
   - **NetSuite:** Reports, then Financial, then Trial Balance; set the period; Export, then CSV.
   - **Sage Intacct:** General Ledger, then Reports, then Trial balance; set the as-of date; Run; Export, then CSV.

   Each ends with "Upload the file here".
5. **Synthetic fixtures:** `qbd_trial_balance_xlsx`, `netsuite_trial_balance_csv` and `intacct_trial_balance_csv` in `abacus_tools/synthetic/ledger_exports.py`, from the same generated trial balances as QBO and Xero (ADR-085).
6. **Tests:**
   - each format parses (codes, names, signs, parenthesised negatives, thousands separators, the total row, the period end);
   - wrong-system files are refused with the right `looks_like_<system>`;
   - each format's period edge cases;
   - the import endpoint accepts each one;
   - a local smoke importing each on a Dev engagement.

### Questions for the human
- **D1: layouts without real samples.** I've no real exports from these three systems. I recommend shipping them built from documented layouts and synthetic fixtures, as QBO and Xero were, and asking you for anonymised samples. Any sample that doesn't parse becomes a quick fix to the format's configuration. The alternative is to wait for samples first.
- **D2: NetSuite periods by month.** I recommend reading "End of Dec 2026" or "Dec 2026" as December 31, 2026 (the month's last day), which the year-end check then compares.
- **D3: one file type each for now:** QuickBooks Desktop Excel, NetSuite CSV, Sage Intacct CSV. These are the exports each system makes most readily. Others can be added on request.
- **D4: approval file:** `backend/src/abacus/modules/connections/**`, `backend/tests/unit/**`, `backend/tests/integration/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-14` — Design written for founder review after SPEC-033 completed (#119).
- `2026-10-14` — Built (D1–D4): three formats; code style `column`; " · " and " - " separators; month periods; synthetic fixtures. Unit tests (10,295, with 33 new: each format, NetSuite's month and amount headers, every wrong-system pair refused by name, the steps) and gates pass. Local smoke: each format imported on a new Dev engagement as `received`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
Done. When the founder shares anonymised real exports from these systems, run each through `parse_export` and adjust the format's configuration if it doesn't read.
