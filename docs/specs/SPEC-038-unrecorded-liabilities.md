---
id: SPEC-038
title: "Fieldwork, part 2: the search for unrecorded liabilities, on payments after year end"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-042, ADR-050, ADR-052, ADR-110, ADR-111, ADR-131, ADR-132]
related_specs: [SPEC-028, SPEC-034, SPEC-036, SPEC-037]
created: 2026-10-19
updated: 2026-10-19
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
The **search for unrecorded liabilities** (SURL) tests completeness of payables. The auditor takes payments made after year end, selects the larger ones, and checks each one's support. Payments for goods or services received before year end should have been recorded as liabilities at year end; if they weren't, that's an exception.

This spec adds it as the second fieldwork procedure, on SPEC-037's machinery (ADR-131, ADR-132):
- **a subsequent-period ledger import:** the general ledger from the day after year end to a cut-off date, which the year-scoped import refuses today;
- **population (code):** payments out of the bank accounts in that window, tied to the import;
- **selection (code):** each payment at or above its **timing band's threshold**, where the threshold rises as the payment gets further from year end (as in the workpaper you shared), plus people's picks;
- **a recorded-at-year-end check (code):** for each selected payment, whether the year-end ledger holds a matching bill for the same supplier and amount;
- **results, conclusion and the workpaper:** as for journal entry testing, with one more field per entry, whether it relates to the year (yes, no or unclear).

## 2. Problem and context
- **The ledger import refuses lines outside the year** (TASK-069's `period_mismatch`). The subsequent period needs its own import, with its own period, that never mixes with the year's snapshot.
- **The year's general ledger is already reconciled** (SPEC-034). It holds the payables account's bills by supplier and reference, so code can tell whether a payment's bill was recorded by year end.
- **The workpaper and sign-off machinery exist** (TASK-084), as do people's picks, results and support requests.
- **Not every account is a bank account.** Exports don't carry account types, so code needs to be told which accounts are bank accounts (Q3).

## 3. Actors
| Actor | Role here |
|---|---|
| Client | Exports the general ledger from the day after year end to the cut-off date, and uploads it (as for SPEC-034) |
| Engagement partner, manager | Set the window, the timing bands and their thresholds; review and sign |
| Senior, staff | Run the procedure, inspect support for each payment, record whether it relates to the year and the result, prepare the workpaper |
| The platform (code) | Imports and ties out the subsequent period, builds the payment population, selects by timing band, checks for a recorded bill, renders the workpaper |

## 4. Goals and non-goals
**Goals**
1. **The subsequent-period import** (connections and ledger):
   - **the same five formats** as SPEC-034, uploaded on the Fieldwork tab;
   - **its period** runs from the day after year end to a cut-off date chosen by the firm (Q2);
   - **parsed in isolation and fingerprinted**, as general ledger imports are;
   - **checked** with period, balance and no-duplicate checks, but no reconciliation to a trial balance: there's no trial balance at the cut-off date (Q1);
   - **stored as an immutable `subsequent_gl` snapshot**, separate from the year's.
2. **Bank accounts:** the firm marks which of the engagement's accounts are bank accounts. The default comes from account names containing "cash", "bank", "checking", "savings" or "money market"; a person confirms or changes it (Q3).
3. **Population (code, ADR-132):** every entry in the subsequent snapshot that credits a bank account, as a payment, with date, supplier, reference, description and amount. It must tie to the snapshot's total of bank-account credits.
4. **Selection (code):**
   - **timing bands,** each a date range after year end with its own threshold (default: the first month at performance materiality × 10%, the second at 25%, the rest at 100%) (Q4);
   - **a payment is selected** when it's at or above its band's threshold;
   - **plus people's picks,** with reasons;
   - **a version and the parameters are recorded,** so the selection is re-performable.
5. **The recorded-at-year-end check (code):** for each selected payment, look in the year's general ledger snapshot for a bill or credit to the payables account (Q5) from the same supplier for the same amount, dated on or before year end. If one exists, the payment is marked "bill recorded at year end (reference …)"; otherwise "no matching bill found". This is a fact for the person, not a conclusion.
6. **Per entry, the person records:**
   - **relates to the year:** yes, no or unclear;
   - **the result:** supported, exception or not tested. An exception is typically "relates to the year, no liability recorded".
   - **support:** evidence links and support requests, as in TASK-084.
7. **The workpaper:** "Search for unrecorded liabilities". It has the same sheets as journal entry testing, plus the timing bands, the bank accounts used, the subsequent period's tie-out and the recorded-at-year-end column. The not-performed list is empty.
8. **Screens:** a second procedure on the Fieldwork tab: upload the subsequent ledger, bank accounts, bands, selection, entries and the workpaper.
9. **The flag** `fieldwork.procedures` covers it.

**Non-goals**
- Bank statements as the source of payments (later, if firms ask).
- Matching to an aged payables report (AP aging) file: the general ledger's payables account is the record here.
- Agents: the TASK-085 assessor may later read invoices for the service date, under SPEC-036's gates.
- Unpaid invoices received after year end (the other half of some firms' SURL). Firms request them as ordinary requests for now.

## 5. User stories and acceptance criteria
**Story: Priya searches for unrecorded liabilities.** Fieldwork is in March; the year ended December 31. The client uploads the general ledger for January 1 to March 15. Abacus finds 2,140 payments from the three bank accounts, tied to the export. With performance materiality of $375,000, the bands select payments over $37,500 in January, $93,750 in February and $375,000 in March: 6 payments, one of which Priya adds herself. For two of them the year-end ledger already holds the bill. For the other four, Priya checks the invoices. One is for December consulting with no bill recorded: an exception.

- **AC-1** Given a subsequent-period export, then it's parsed in isolation, checked (every line inside the window, debits equal to credits, not a duplicate), and stored as an immutable snapshot that never mixes with the year's.
- **AC-2** Given confirmed bank accounts, then the population is every entry crediting them in the window, tied to the snapshot's bank-account credits. Without confirmed bank accounts, nothing is selected.
- **AC-3** Given bands and thresholds, then selection is a pure function: the same snapshot and parameters give the same payments, each with its band.
- **AC-4** Given a selected payment, then code shows whether the year-end ledger holds a matching bill, by supplier, amount and a date on or before year end, as a fact. People record whether it relates to the year, and the result.
- **AC-5** Given the procedure, then its workpaper renders deterministically and signs off as ADR-131 requires.
- **AC-6** Given a client, then they upload the export, and nothing else of the procedure is visible to them.
- **AC-7** Given every new screen, then loading, empty, error and not-allowed states exist.

## 6. Design notes
- **Where:**
  - the subsequent import in connections (it reuses `gl_parse`), and its snapshot in ledger (`subsequent_gl_snapshots`, `subsequent_gl_entries`, insert-only and immutable);
  - bank accounts, the population, the bands and the check in `sampling`;
  - the procedure definition `unrecorded_liabilities` in `fieldwork`.
- **Data:**
  - `engagement_bank_accounts` (versions);
  - the procedure's parameters hold the window and the bands;
  - `selected_items` gains `band` and `recorded_bill` (reference, date) for this definition;
  - `item_results` gains `relates_to_year`.
- **Permissions:** existing ones (`procedure.*`, `workpaper.*`, `ledger_import.upload` for the client's upload).

## 7. Delivery
- **TASK-086 (red):** the subsequent-period import and snapshot, and bank accounts.
- **TASK-087 (red):** the population, bands, selection and the recorded-bill check, results with relates-to-year, the workpaper, and the screens.

## 8. Test plan
| AC | Level | What |
|---|---|---|
| AC-1 | unit, integration | Parsing in isolation; window, balance and duplicate checks; immutability |
| AC-2, AC-3 | unit (property) | Tie-out; bands select exactly; determinism |
| AC-4 | unit | Matching bills found and not found; amounts exact |
| AC-5 | unit | Deterministic bytes; sign-off as TASK-084 |
| AC-6 | integration | Client roles refused beyond the upload |
| AC-7 | vitest | States |

## 9. Open questions
All resolved: the founder approved every recommendation below on 2026-10-19.
- **Q1: completeness of the subsequent export.** There's no trial balance at the cut-off date to reconcile against. *Recommendation:* check what we can by code: lines inside the window, balance, each month in the window with activity, and no duplicate file. The workpaper says plainly that completeness rests on the client's export, with its fingerprint. A later option is reconciling bank-account movement to bank statements.
- **Q2: the cut-off date.** *Recommendation:* the firm sets it (usually the fieldwork or report date). It defaults to 90 days after year end, and is at least 30.
- **Q3: identifying bank accounts.** *Recommendation:* a suggestion by account name, which a manager or partner confirms per engagement; selection waits for that confirmation.
- **Q4: default bands.** *Recommendation:* first month 10%, second month 25%, then 100% of performance materiality. Firms edit them in their fieldwork defaults, and each procedure records its own.
- **Q5: the payables account.** *Recommendation:* chosen like bank accounts, suggested by names containing "payable" or "accounts payable" and confirmed by a person. The check looks for a bill or credit to it from the same supplier, for the same amount.
