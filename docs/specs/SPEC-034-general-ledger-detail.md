---
id: SPEC-034
title: "General ledger detail: importing transactions, reconciling them to the trial balance, and the journal listing"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-016, ADR-038, ADR-050, ADR-052, ADR-085, ADR-103, ADR-107, ADR-110]
related_specs: [SPEC-000, SPEC-006, SPEC-022, SPEC-028]
created: 2026-10-14
updated: 2026-10-15
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
Today the platform holds only trial balances, so it can test balances but not the transactions behind them. This spec adds the **general ledger detail**: every posting for the fiscal year, imported from the client's accounting system export as trial balances are (SPEC-028).

Before anything relies on the detail, **code proves it is complete** (ADR-038, ADR-050):
- for each account, the opening balance plus the year's activity equals the closing balance in the year-end trial balance;
- the detail reconciles to that trial balance;
- every month of the period is covered.

A detail that passes is kept as an immutable snapshot. It fulfils the engagement's **general ledger** and **journal listing** requests, rendered as workbooks with the reconciliation on their first sheet. Nothing here uses a model. Sampling and journal-entry testing build on it later.

This is the GL part of Act 2's A1 (SPEC-028 Q5).

## 2. Problem and context
- **Ledger** stores trial balance snapshots only. ADR-038's other two checks, opening plus activity equals closing and GL-to-TB reconciliation, wait for GL data (ledger README).
- **Requests already recognise these items.** Classification has `general_ledger` ("general ledger", "GL detail") and `journals` ("journal entries", "journal listing") as tier A datasets. Nothing can deliver them, so they stay open and the client must send files the firm can't verify.
- **File import exists** (SPEC-028): formats as configuration, malware scanning, parsing in an isolated child process with limits, write-once storage, validation, snapshots, rendering, and fulfilment of tier A items. Five systems are supported for trial balances.
- **Size.** A small company's GL is tens of thousands of lines; a mid-sized one can pass a million. The trial balance path keeps everything in memory, which is fine at a few hundred lines but not at this size.

## 3. Actors
| Actor | Role here |
|---|---|
| Client admin | Exports the GL detail from their system and uploads it, as for the trial balance |
| Engagement partner, manager, senior | May upload on the client's behalf (SPEC-028 Q4); see the import, its checks and the evidence |
| The platform (code) | Scans, parses in isolation, checks completeness against the trial balance, snapshots, renders, fulfils |

## 4. Goals and non-goals
**Goals**
1. **GL detail formats** (configuration, as SPEC-028):
   - **QuickBooks Online** "General Ledger" (CSV) and **Xero** "General Ledger Detail" (XLSX) first (Q1);
   - each line gives: account (code and name), date, transaction type, reference number, name (customer or vendor), description, debit and credit (or signed amount);
   - per account, the opening balance line and the closing total where the export has them;
   - guided export steps per system.
2. **Upload** on the same "Export instead" path as the trial balance. It's a second file for the same period: "General ledger detail", with a 50 MB limit (Q2, amended 2026-10-15; the trial balance's stays as it is). It goes through the same scan, isolation (with a longer time limit) and write-once storage.
3. **Normalise** to a common model: `GlEntry` (account code, date, transaction reference, type, counterparty, description, debit, credit, source row) per line, plus each account's opening balance.
4. **Completeness checks by code** (ADR-038), in order:
   - `period_mismatch`: lines outside the fiscal year, or no line in a month the TB shows activity for (Q3);
   - `unbalanced`: the detail's total debits differ from its total credits;
   - `roll_forward`: for an account, opening plus debits minus credits differs from its year-end trial balance closing balance (to the cent);
   - `missing_account`: an account with a TB balance but neither detail nor an opening balance;
   - `extra_account`: detail for an account the TB doesn't have.

   This needs an imported or retrieved year-end trial balance for the same entity and period. Without one, the detail is held as "waiting for the trial balance", and is checked when one arrives (Q4). A failure gives a plain, fixed message naming the first few accounts that don't roll forward, with amounts computed by code.
5. **Snapshot** (ledger): `gl_snapshots` (entity, period, source, raw fingerprint, the trial balance snapshot it reconciles to, line count, totals) and `gl_entries` (the lines). Both are insert-only and immutable, as trial balance snapshots are (ADR-004). The same file again creates no second snapshot.
6. **Render** two evidence workbooks, deterministic, as the trial balance is:
   - **General ledger:** a reconciliation sheet (account, opening, debits, credits, closing, TB closing, difference) and the detail by account;
   - **Journal listing:** the same postings grouped by transaction (date, reference, type, lines, totals) (Q5).
7. **Fulfil** the engagement's open tier A items for `general_ledger` and `journals` for that period, as a retrieval does.
8. **Screens:** the "Export instead" panel gets a second upload, "General ledger detail", with its steps and status:
   - waiting for the trial balance;
   - received, with N transactions and a reconciled tick;
   - failed, with the reason.

   The firm sees the import and its reconciliation on the request item.

**Non-goals**
- Retrieving GL detail through a live connector (the connector work, staging).
- Sampling, journal-entry testing or analytics on the detail (later specs, which build on `gl_entries`).
- NetSuite, Sage Intacct and QuickBooks Desktop GL formats (a follow-up, as with the trial balance).
- Sub-ledgers (AR and AP detail by invoice) and multi-currency ledgers (USD only, SPEC-028 Q3).
- Editing or correcting lines: a wrong export is replaced by a new upload.

## 5. User stories and acceptance criteria
**Story — Rachel sends the GL; Priya can rely on it.** Rachel already uploaded the year-end trial balance. She follows the steps for "General ledger detail", exports the year from QuickBooks Online, and uploads the CSV. A minute later the panel says "Received: 18,412 transactions, reconciled to the trial balance". Priya opens the "General ledger" request and sees the workbook. Its first sheet shows every account rolling forward to the trial balance with zero difference.

- **AC-1** Given "Export instead", then the client can upload a general ledger detail file for the period, with its system's steps, alongside the trial balance.
- **AC-2** Given an uploaded GL file, then it's scanned before parsing, stored write-once with its fingerprint, and parsed in isolation with limits suited to its size. A crash or timeout is `unreadable`, never a worker failure.
- **AC-3** Given a parsed GL and the period's year-end trial balance, then code checks the period coverage, balance, roll-forward per account, and missing and extra accounts. Only a GL that passes every check is snapshotted.
- **AC-4** Given no trial balance yet, then the GL is held as waiting, and it's checked as soon as a trial balance for that entity and period is snapshotted.
- **AC-5** Given a failed check, then the client sees a fixed message naming the first accounts that don't reconcile and by how much. Nothing is snapshotted or fulfilled, and the firm sees the same.
- **AC-6** Given a snapshotted GL, then the general ledger and journal listing workbooks are rendered deterministically (the same snapshot gives the same bytes). They fulfil the open tier A `general_ledger` and `journals` items for the period, with method `imported`.
- **AC-7** Given the same file again, then no second snapshot is made. Given a corrected file, then a new snapshot replaces the old one as the items' evidence (a new version; nothing is deleted).
- **AC-8** Given GL snapshots and entries, then the app can't update or delete them (grants and triggers), and entries can only be inserted with their snapshot.
- **AC-9** Given every new screen, then loading, empty, error and not-allowed states exist, and colours come only from tokens.

## 6. Design notes
- **Ledger** gains `GlEntry`, `NormalisedGeneralLedger`, `validate_gl(gl, tb, period) -> str | None`, `record_gl_snapshot(...)` and `gl_snapshot_view(...)`. These are pure checks and insert-only tables. Ledger still depends on no module.
- **Connections** gains GL formats (configuration beside the trial balance formats), streaming row parsing in the isolated child, and import records linking to the TB snapshot they reconcile to. A waiting GL is retried on `ledger_snapshot.created` for the same entity and period.
- **Evidence** renders the two workbooks (`render.py`) from `gl_snapshot_view`.
- **Scale:**
  - rows are parsed and inserted in batches (COPY, or multi-row inserts of a few thousand);
  - the workbooks are written in streaming mode;
  - limits are 1,000,000 lines and 50 MB (Q2, amended).
  - Workbooks over Excel's row limit are split across sheets.
- **Flag** `ledger.gl_import` (off; on for the Dev firm).

## 7. Delivery
- **TASK-069 (red):** ledger model, checks, snapshots and tables; QBO and Xero GL formats; streaming parse; the waiting state; synthetic GL fixtures generated from synthetic trial balances (ADR-085), so they reconcile by construction, with deliberate flaws for each failure.
- **TASK-070 (amber):** rendering both workbooks, fulfilment, and the screens.

## 8. Test plan
| AC | Level | What |
|---|---|---|
| AC-2 | unit, integration | Scan before parse; isolation limits; crash is `unreadable` |
| AC-3, AC-5 | unit (property tests) | Any synthetic GL generated from a TB reconciles; each flaw (missing month, one-cent drift, missing account, extra account, unbalanced) gives its code and message |
| AC-4 | integration | GL first, TB later: checked and snapshotted on the TB's arrival |
| AC-6 | unit | Deterministic bytes; reconciliation sheet totals; journal grouping |
| AC-7, AC-8 | integration | Duplicate file; replacement; grants and triggers |
| AC-9 | vitest | The panel's states |
| — | performance | 1,000,000 synthetic lines parse, check and snapshot within the isolation limits |

## 9. Open questions
All resolved: the founder approved every recommendation below on 2026-10-14.
- **Q1 — first formats.** *Recommendation:* QuickBooks Online (CSV) and Xero (XLSX), as for the trial balance. QuickBooks Desktop, NetSuite and Sage Intacct follow in one task once these work.
- **Q2 — size limits.** *Recommendation:* 100 MB and 1,000,000 lines for a GL file, with a 5-minute isolation limit. Larger ledgers would need a connector or splitting by quarter, a later feature. *Amended 2026-10-15 (founder):* 50 MB for now, the platform's storage cap (about 750,000 lines in QuickBooks Online's layout); raising it is a later, separate change.
- **Q3 — period coverage.** *Recommendation:* every line must fall within the fiscal year, and every month in which the trial balance shows activity on an income statement account must have at least one line. A month with none suggests a partial export. Balance sheet-only months aren't required.
- **Q4 — order of uploads.** *Recommendation:* accept the GL before the trial balance, hold it as "waiting for the trial balance", and check it automatically when the trial balance arrives. Clients won't always upload in order.
- **Q5 — the journal listing.** *Recommendation:* derive it from the same GL detail, grouping lines by transaction reference and date, rather than asking for a second export. One file then fulfils both requests, and the journal totals are proven by the same reconciliation.
- **Q6 — opening balances.** Some exports print each account's opening balance; others don't. *Recommendation:* use the export's opening balance when present. Otherwise, take it as the closing balance minus the year's activity only for balance sheet accounts, flagged "opening balance derived" (the roll-forward then can't fail for that account and says so), and zero for income statement accounts. Prior-year TB comparison is a later check.
