---
id: TASK-086
title: "Unrecorded liabilities, part 1: the subsequent-period ledger import, and bank and payables accounts"
spec: SPEC-038
acceptance_criteria: [AC-1, AC-2, AC-6]
risk_zone: red
status: done
branch: task-086-087-surl
worktree:
created: 2026-10-19
updated: 2026-10-19
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-038 §7, TASK-086. A general ledger export covering the day after year end to a cut-off date can be uploaded and checked. It's stored as an immutable snapshot that never mixes with the year's. A manager or partner confirms which accounts are bank accounts and which is the payables account.

## Plan
- [x] Plan approved by human (founder, 2026-10-19: "focus on build and shipping quickly", designs as recommended). Approved by founder: the paths named in TASK-086 D3

### What the code shows
- **The year's import:** `receive_gl_export` stores and scans the file, then `GlImportWorkflow` runs `process_gl_import`. That parses in isolation, waits for a trial balance, reconciles (`validate_gl`), and snapshots into `gl_snapshots` and `gl_entries`, which are immutable and require a trial balance snapshot.
- **The parser already counts lines outside a given window** (`outside_period`), so it works for any window.

### Design (for founder review)
1. **The same tables, a new kind (D1).** Migration 0060 adds:
   - `gl_snapshots.kind` (`year` or `subsequent`), with `tb_snapshot_id` nullable only for `subsequent`;
   - `gl_imports.kind`.

   The year's readers (`latest_gl_snapshot`, the workbooks, journal entry testing) filter on `kind = 'year'`, so the two never mix. The immutability triggers and grants stay as they are.
2. **The import:**
   - `POST …/connection/import/gl?format=&kind=subsequent&cutoff=YYYY-MM-DD` (`ledger_import.upload`), with the same scan, storage and duplicate checks;
   - the period runs from the day after year end to the cut-off, which must be 30 to 366 days after year end (default 90, as SPEC-038 Q2 says);
   - `process_gl_import` branches on the kind, with no trial balance wait and no reconciliation (Q1). It refuses with:
     - `period_mismatch` for any line outside the window, or a month in the window with no lines (the cut-off month may be partial);
     - `unbalanced`;
     - the usual parse failures.
   - A passing file becomes a `subsequent` snapshot with its entries;
   - `GET …/connection/import/gl?kind=subsequent` returns its status.
3. **Bank and payables accounts** (fieldwork; `engagement_accounts`, insert-only, the newest is current):
   - each row holds a role (`bank` or `payables`), the account codes, who confirmed and when;
   - `GET …/fieldwork/accounts` returns the confirmed accounts, and suggestions from the year's snapshot account names: "cash", "bank", "checking", "savings" or "money market" for bank; "payable" for payables;
   - `PUT …/fieldwork/accounts` (`procedure.configure`: partner, manager) confirms them.
4. **Screens:** the Fieldwork tab's unrecorded-liabilities card gets a "General ledger after year end" upload (format, cut-off date and file, with status), and account confirmation with the suggestions ticked.
5. **Tests, kept light as you asked:** the parser window and the subsequent checks on a synthetic subsequent ledger; the year's readers ignoring `subsequent`; a local smoke.

### Questions for the human
- **D1 — storage.** Recommended: the same immutable tables with a `kind` column. The alternative is separate tables, which duplicates the triggers, grants and readers.
- **D2 — who uploads.** Recommended: the firm uploads first, on the Fieldwork tab. Client upload, through the client's accounting system panel, comes in a later small task.
- **D3 — approval file:** `backend/src/abacus/modules/connections/**`, `backend/src/abacus/modules/ledger/**`, `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`, `backend/tests/unit/**`.

## Definition of done
- [ ] Gates pass; the listed ACs have tests where useful (founder: light testing)

## Progress log
- `2026-10-19` — Design written with TASK-087.
- `2026-10-19` — Built (D1–D3): migration 0060 (`gl_snapshots.kind` and `gl_imports.kind`, `tb_snapshot_id` null only for `subsequent`); `ledger.validate_subsequent`, `record_subsequent_snapshot`, `latest_subsequent_snapshot` (year readers filter `year`); `receive_gl_export(kind, cutoff)` and `_process_subsequent` (no trial balance; window, months, balance); the year's workbooks skip subsequent imports; `engagement_accounts` with suggestions by name; the upload and accounts panels. Gates pass; focused tests only (founder: light testing). Local smoke: a cut-off 15 days after year end refused; a QuickBooks export for January to March checked and snapshotted; bank 1000 and payables 2000 suggested and confirmed.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
Done.
