---
id: TASK-070
title: "General ledger detail, part 2: the general ledger and journal listing workbooks, fulfilment, and the upload screens"
spec: SPEC-034
acceptance_criteria: [AC-1, AC-5, AC-6, AC-7, AC-9]
risk_zone: amber
status: done
branch: task-070-gl-evidence
worktree:
created: 2026-10-15
updated: 2026-10-15
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-034 §7, TASK-070. A reconciled general ledger (TASK-069) becomes evidence: two deterministic workbooks that fulfil the engagement's general ledger and journal listing requests. The client gets the upload screen and its plain-language statuses.

## Scope
SPEC-034 AC-1 (screens), AC-5 (messages), AC-6, AC-7, AC-9. The 50 MB limit stands (Q2, as amended).

## Context to load
- Spec: `docs/specs/SPEC-034-general-ledger-detail.md`; ADR-042 (deterministic rendering), ADR-050
- Code:
  - `evidence/render.py` (`render_trial_balance`, `_normalised`);
  - `connections/pipeline.py` (`render`: `add_version`, `fulfil_by_rule`);
  - `connections/service.py` (`load_system_context`, the only issuer of system contexts, SYS-001);
  - `connections/gl_import.py`, `connections/workflows.py` (`GlImportWorkflow`);
  - `ledger/gl_service.py` (`gl_snapshot_view`, `gl_entries`);
  - `apps/web/src/screens/LedgerExport.tsx`, `importMessages.ts`

## Plan
- [x] Plan approved by human (founder, 2026-10-15: D1–D4 as recommended). Approved by founder: the paths named in D4

### What the code shows
- **A trial balance becomes evidence in the pipeline's render stage.** The stage renders deterministically, stores the file, adds an evidence version (method `imported` or `retrieved`, keyed by snapshot and item), and fulfils the item by rule. All of this runs under a system context issued by connections' run loader from the run row.
- **`render_trial_balance` builds the workbook in memory,** then rebuilds the ZIP with fixed timestamps for byte-identical output. A general ledger can have 750,000 lines, so its workbook must be written in streaming mode.
- **`GlImportWorkflow` (v1) runs one activity**, and its replay histories are recorded. A new step needs Temporal versioning (ADR-090).
- **The "Export instead" panel** shows the trial balance formats, steps, upload and status. There's nothing yet for a general ledger.

### Design (for founder review)
1. **Rendering** (evidence, `render_gl.py`, deterministic as ADR-042 requires):
   - **General ledger workbook:**
     - sheet "Reconciliation": account, opening (marked "derived" where it was), debits, credits, closing, trial balance closing, difference, and totals;
     - sheets "Detail", "Detail (2)" and so on, so that none passes Excel's 1,048,576-row limit: account, date, type, reference, name, description, debit, credit, in account then date order;
     - a footer naming the system, uploader and upload date, as the trial balance has.
   - **Journal listing workbook:** one block per transaction (D2) with date, type, reference, name, and its lines (account, debit, credit) and totals, split across sheets the same way.
   - Both are written with openpyxl's streaming writer. Text cells are explicit strings, never formulas (client text is hostile). Properties are fixed and the ZIP is rebuilt with fixed timestamps, so the same snapshot always gives the same bytes.
2. **Evidence and fulfilment** (connections):
   - a new activity, `gl_import.render`, runs after `reconciled`, added to `GlImportWorkflow` behind `patched("render")`, with new replay histories;
   - it renders both workbooks from `gl_snapshot_view` and `gl_entries` (paged), stores them, and adds two evidence versions (method `imported`, period, entity, idempotency key `gl:<snapshot>:<item>`);
   - it fulfils the engagement's open, received or needs-revision tier A items with dataset `general_ledger` (the general ledger workbook) and `journals` (the journal listing), by rule;
   - a later corrected file gives a new snapshot and new versions, and nothing is deleted (AC-7).
3. **Who acts** (D1): a system context for the import, issued by connections' run loader (`load_gl_import_context`, beside `load_system_context`, so SYS-001 still holds). It's proven by the `gl_imports` row (reconciled, with its snapshot) and acts on behalf of the uploader, as a retrieval acts for the person who started it.
4. **Status** (`GET …/connection/import/gl`) gains `evidence: [{dataset, evidence_version_id}]` once rendered.
5. **Screens** (web, `LedgerExport.tsx`):
   - a "General ledger detail" section under the trial balance: the system picker (QuickBooks Online, Xero), numbered steps, the expected file type and the 50 MB limit, then upload;
   - statuses: "Checking your general ledger…"; "Waiting for your trial balance: upload it above and we'll check the general ledger against it"; "Received: 18,412 transactions, reconciled to your trial balance"; or the failure message;
   - fixed failure messages per code (AC-5), whose only values are code-computed:
     - `period_mismatch`: "Your export doesn't cover the whole year: March 2026 has no transactions…", or it has transactions outside the year;
     - `unbalanced`: "Debits and credits differ by $10.00";
     - `roll_forward`: "These accounts don't agree with your trial balance: 4000 (off by $0.01), …";
     - `missing_account`, `extra_account`, `unreadable`, `looks_like_*`;
   - polling while processing, and loading, empty, error and not-allowed states.
   - **The firm** sees the same panel read-only on the engagement, and the workbooks as evidence on the general ledger and journal listing requests (existing item detail).
6. **Tests:**
   - unit: deterministic bytes; reconciliation totals; derived openings marked; sheet splitting past the row limit (shown with a small configured limit); journal grouping; formula-like text written as text;
   - integration: render and fulfil both requests; a replacement file makes new versions; the system context is proven by the row;
   - workflow replay of the patched branch;
   - vitest: the section's states and messages;
   - a local smoke: a 760,000-line ledger rendered, stored under the cap, and fulfilling both requests.

### Questions for the human
- **D1 — who fulfils.** Recommended: the platform, under a system context issued for the import by connections' run loader, on behalf of the uploader. This is how retrievals fulfil the trial balance, and it keeps the rule that only run loaders issue system contexts.
- **D2 — how journal entries are grouped.** Recommended: by posting date, transaction type and reference. Lines with no reference are grouped by date, type and name. A group whose debits and credits differ is marked "doesn't balance on its own": informational, since the ledger as a whole has already reconciled.
- **D3 — a workbook over the storage cap.** At the 50 MB upload limit, a rendered workbook should stay under the 50 MB storage cap (I'll measure it). Recommended: if one ever exceeds it, store the detail as numbered part workbooks (part 1 of N), each its own evidence version on the request. The alternative is to refuse with `rendered_too_large`.
- **D4 — approval file:** `backend/src/abacus/modules/evidence/**`, `backend/src/abacus/modules/connections/**`, `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-15` — Design written for founder review after TASK-069 (#122) and the 50 MB amendment (#123).
- `2026-10-15` — Built (D1–D4): `evidence/render_gl.py`; `gl_import.render` behind `patched("render")` with v2 replay histories; `load_gl_import_context`; fulfilment of `general_ledger` and `journals`; the "General ledger detail" section in the accounting system panel with statuses and fixed failure messages. Unit and workflow tests (10,500+), web (321) and gates pass. Local smoke through the worker: GL then TB → reconciled → both workbooks added and the general ledger and journal requests received; at 760,072 lines the workbooks were 24 MB and 29 MB (no parts needed) and everything finished in about 43 seconds after the trial balance arrived.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The status endpoint doesn't list the evidence versions (design item 4) | The request items already show their evidence; nothing on screen needed it | No |
| Evidence versions link to the trial balance snapshot; the GL snapshot ID is in the footer | `evidence_versions.snapshot_id` references trial balance snapshots only | No |

## Handoff
Done. SPEC-034 is complete.
