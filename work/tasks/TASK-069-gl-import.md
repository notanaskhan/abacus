---
id: TASK-069
title: "General ledger detail, part 1: formats, isolated parsing at scale, the completeness checks and immutable GL snapshots"
spec: SPEC-034
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-7, AC-8]
risk_zone: red
status: done
branch: task-069-gl-import
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
SPEC-034 §7, TASK-069: a general ledger export is uploaded, parsed, and proven complete against the year-end trial balance by code. If it passes, it's kept as an immutable snapshot. The workbooks, fulfilment and screens follow in TASK-070.

## Scope
SPEC-034 AC-1 (the upload endpoint), AC-2, AC-3, AC-4, AC-5 (the API's reasons), AC-7, AC-8.

## Context to load
- Spec: `docs/specs/SPEC-034-general-ledger-detail.md`; ADR-004, ADR-038, ADR-050, ADR-052, ADR-110; SPEC-028
- Code:
  - `connections/ledger_import.py` (`receive_export`, `check_export`, `_retrieve`), `connections/import_formats.py`, `connections/import_parse.py`, `connections/pipeline.py` (where trial balance snapshots are recorded);
  - `ledger/normalise.py`, `ledger/service.py` (`record_snapshot`, `snapshot_view`), `ledger/models.py`, and the immutability triggers in `migrations/versions/0009_*`;
  - `kernel/isolation.py`; `abacus_tools/synthetic/ledger_exports.py`, `abacus_tools/synthetic/model.py`

## Plan
- [x] Plan approved by human (founder, 2026-10-14: D1–D4 as recommended). Approved by founder: the paths named in D4

### What the code shows
- **A trial balance export is handled entirely inside the request.** It's scanned, staged, parsed in an isolated child (30 seconds, 20 CPU seconds, 1 GB), validated and recorded. The retrieval pipeline then snapshots it. A general ledger can be a hundred times larger and take minutes, which a request can't hold.
- **`run_isolated` has fixed limits,** and returns the child's result by pickling. A million parsed lines shouldn't cross that way.
- **Trial balance snapshots are recorded in the connections pipeline.** Nothing announces them, so a general ledger waiting for one has nothing to listen to.
- **Ledger tables are insert-only and immutable:** grants plus a trigger refusing UPDATE, DELETE and TRUNCATE for every role, and lines insertable only in their snapshot's transaction.

### Design (for founder review)
1. **Upload** (connections): `POST …/connection/import/gl?format=` (`ledger_import.upload`; flag `ledger.gl_import`).
   - The same steps as the trial balance: the flag, permission and client data gate before the body is read; up to 100 MB; scanned before anything parses it; staged write-once; a duplicate fingerprint returns the existing import.
   - It records a **`gl_imports`** row with status `processing` and starts the **`GlImport` workflow** (D1). The response is immediate, with that status.
2. **`GlImport` workflow** (connections, `gl_import:<tenant>:<import>`, batch work class), one activity per stage:
   - **parse:** in an isolated child with the GL limits (D3). The child streams the file and writes the normalised lines to a private temporary file (D2). It returns only a summary: line count, per-account opening, debits, credits, months with activity, and the parse failure if any.
   - **check:** `ledger.validate_gl(summary, tb)` against the latest year-end trial balance snapshot for the entity and period. Without one, the status becomes `waiting_for_tb` and the workflow ends.
   - **snapshot:** for a passing summary, one transaction inserts the `gl_snapshots` row, the per-account balances and the lines in batches of 5,000. The temporary file is deleted afterwards whatever happens.
   - **status:** `reconciled` with the snapshot, or `failed` with its code and details.
3. **Waiting for the trial balance (AC-4):** the connections pipeline emits `ledger_snapshot.recorded` (entity, period) after recording a trial balance snapshot. A subscriber restarts `GlImport` for each `waiting_for_tb` import of that entity and period.
4. **Checks** (ledger, pure, ADR-050), in this order, using exact amounts:
   - `period_mismatch`: a line outside the fiscal year, or a month with income statement activity in the trial balance but no lines (SPEC-034 Q3);
   - `unbalanced`;
   - `missing_account`;
   - `extra_account`;
   - `roll_forward`: opening plus debits minus credits differs from the trial balance closing balance.

   The failure details are code-computed: up to five accounts with their difference, or the missing months. Opening balances follow SPEC-034 Q6: the export's own, else derived for balance sheet accounts (flagged `opening_derived`), else zero.
5. **Data** (migration 0051):
   - **ledger:**
     - `gl_snapshots`: entity, period, source, raw fingerprint, the trial balance snapshot, line count, totals, created_at; unique per entity and fingerprint;
     - `gl_account_balances`: snapshot, account code and name, opening, debits, credits, closing, `opening_derived`;
     - `gl_entries`: snapshot, line number, account code, posting date, transaction reference, type, counterparty, description, debit, credit, source row;
     - all insert-only and immutable, as `ledger_snapshots` and `trial_balance_lines` are, and the balances and entries are insertable only in their snapshot's transaction;
     - `gl_snapshots` CHECKs that total debits equal total credits.
   - **connections:** `gl_imports`: engagement, entity, format, period, storage reference, fingerprint, size, status (`processing`, `waiting_for_tb`, `reconciled`, `failed`), failure code, failure details (JSON of codes and numbers only), the GL snapshot, line count, uploaded by, on behalf, timestamps. The app may update only the status columns.
6. **Formats** (configuration, SPEC-034 Q1), with account heading rows, an opening balance row and a total row:
   - **QuickBooks Online "General Ledger" CSV:** account headings ("1000 Checking"), "Beginning Balance", lines with Date, Transaction Type, Num, Name, Memo/Description and a signed Amount, then "Total for 1000 Checking";
   - **Xero "General Ledger Detail" XLSX:** account headings, "Opening Balance", lines with Date, Source, Description, Reference, Debit and Credit, then "Total <account>" or "Closing Balance".
7. **Synthetic general ledgers** (`abacus_tools/synthetic/ledger_exports.py`), generated from a synthetic trial balance so they reconcile by construction:
   - balance sheet accounts open at their closing balance, except cash;
   - income statement postings are spread across the twelve months, each paired with cash;
   - cash's opening balance makes the openings balance.
   - Flaws on request: a missing month, a one-cent drift, a missing account, an extra account, an unbalanced line, a line outside the period.
   - Writers for both formats, including a large-file mode.
8. **Reads:** `GET …/connection/import/gl` gives the latest GL import's status, line count and failure details (codes and numbers; the screen words them in TASK-070).
9. **Tests:**
   - property tests: any synthetic general ledger generated from a trial balance passes, and each flaw gives its code with correct details;
   - both formats parse, including headings, openings, totals, signed amounts and parentheses;
   - isolation limits, with a crash or timeout giving `unreadable`;
   - integration: grants and triggers; a duplicate file; GL first and trial balance later; a replacement file makes a new snapshot;
   - workflow replay histories;
   - a performance run of 1,000,000 synthetic lines within the limits;
   - a local smoke on a Dev engagement.

### Questions for the human
- **D1: asynchronous processing.** Recommended: the upload returns at once as `processing`, and a workflow parses, checks and snapshots, so a large ledger never holds a request open. The trial balance path stays synchronous, which suits its size.
- **D2: moving a million lines out of the isolated child.** Recommended: the child writes the normalised lines to a private temporary file and returns only a summary. The parent inserts them in batches inside the snapshot's transaction and deletes the file in all cases. The alternative is returning everything through the process pipe, which is slow and memory-heavy at this size.
- **D3: isolation limits.** Recommended: `run_isolated` takes per-call limits. General ledgers get 5 minutes, 4 CPU minutes and 2 GB of memory; trial balances and uploads keep today's limits.
- **D4: approval file:**
  - `backend/src/abacus/modules/ledger/**`, `backend/src/abacus/modules/connections/**`;
  - `backend/src/abacus/kernel/isolation.py`;
  - `docs/architecture/feature-flags.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`;
  - `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-14` — Design written for founder review after SPEC-034 merged (#121).
- `2026-10-14` — Built (D1–D4): `kernel.isolation.run_isolated_with`; ledger's GL model, `validate_gl`, `record_gl_snapshot` and reads; migration 0051 (immutable `gl_snapshots`, `gl_account_balances`, `gl_entries`; `gl_imports`); QBO and Xero GL formats; the streaming child parser writing a private temporary file; `GlImportWorkflow` with one activity; `ledger_snapshot.recorded` and the waiting restart; upload, status and formats routes; flag `ledger.gl_import`; synthetic GLs built from trial balances with six flaws; replay histories. Unit and workflow tests (10,499), web (310) and gates pass; 28 new GL tests (five generated trial balances in both formats reconcile; every flaw gives its own check; derived openings; malformed files; the isolated parse).
- `2026-10-14` — Local smoke on the Dev firm through the worker: GL first → `waiting_for_tb`; the trial balance import's snapshot restarted it → `reconciled` (72 lines) in 4 seconds; the same file again was recognised. The app role was refused UPDATE, DELETE and stray INSERTs on GL tables. Scale: 760,072 lines (50 MB) parsed, checked and snapshotted in about 40 seconds. Evidence storage caps a stored file at 50 MB, below SPEC-034's 100 MB: an upload over the cap is refused as `payload_too_large` (question for the founder).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| One activity for parse, check and snapshot | The temporary file lives on the worker that parsed it; separate activities could land on different workers | No |
| Balance sheet versus income statement: an account with a printed opening is balance sheet; with no openings printed at all, accounts numbered 1-3 | Exports don't carry account types | No |
| Month coverage: when any income account has a balance, every month of the year needs a line | A trial balance has no monthly activity to compare against | No |
| An upload over storage's 50 MB cap is refused as `payload_too_large` | Raising the cap needs `evidence/storage.py`, outside this approval | No — founder to decide |

## Handoff
Done. Open: evidence storage's 50 MB cap versus SPEC-034's 100 MB (raising it is a change to `evidence/storage.py`). Next: TASK-070 (workbooks, fulfilment, screens).
