---
id: TASK-054
title: "Upload processing, part 1: scanning every upload, the processing workflow and extraction"
spec: SPEC-029
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: red
status: awaiting-approval
branch: task-054-upload-processing
worktree:
created: 2026-10-12
updated: 2026-10-12
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-029 §8, TASK-054: every upload is malware-scanned before it's stored; each stored upload is processed by an `upload_processing` workflow that extracts its text, tables and key fields in an isolated child process into a derived record. Checks (TASK-055), previews (TASK-056) and the screens (TASK-057) build on it.

## Scope
SPEC-029 AC-1 to AC-4; goals 1, 2, 3 and 9.

## Context to load
- Spec: `docs/specs/SPEC-029-upload-processing.md`; ADR-017, ADR-052, ADR-090, ADR-104, ADR-110
- Code: `evidence/uploads.py` (`checked`, `upload`, `attach`), `evidence/inbox.py` (`add_to_inbox`), `evidence/setup_files.py`, `evidence/storage.py`, `evidence/api.py`; `kernel/scanning.py`; `connections/import_parse.py` (`parse_isolated`); `connections/workflows.py`, `activities.py`, `auto_retrieval.py` (workflow and subscriber patterns); `worker/__main__.py` (`MODULES`)

## Plan
- [ ] Plan approved by human

### What the code shows
- **All three upload paths share `checked()`** (item uploads, inbox files, the firm's setup files), which checks size, type by leading bytes, and fingerprint. None scans.
- **The worker loads workflows from `MODULES = (connections, agents, notifications, communications)`** in `worker/__main__.py` (protected). Evidence has no workflows, activities or subscriptions yet.
- **`parse_isolated`** (TASK-052) already runs a parser in a spawned child process with CPU, memory and time limits, but it lives in `connections`.
- **Uploads announce themselves:** `EvidenceUploaded` (item uploads and inbox assignment) and `InboxFileAdded` go through the outbox.
- `pdfplumber` is *pending* on the allowlist; SPEC-029 Q1 approved it with `pypdfium2`.

### Design (for founder review)
1. **Scanning (AC-1), always on:** `checked()` calls `kernel.scanning.scan` after the size and type checks and raises `UploadRefused` (`file_refused`, 422). Each caller audits the refusal (`upload.refused`, target the engagement, size only) and stores nothing. This covers item uploads, inbox files and setup files.
2. **The workflow** `UploadProcessing` (evidence module), one per evidence version or inbox file, started by evidence's own subscribers to `evidence.uploaded` and `inbox_file.added` when the firm's `uploads.processing` flag is on. Workflow ID `upload:<kind>:<id>`, so an at-least-once event starts it once. Activities: `extract` (isolated), then `record`. TASK-055 and TASK-056 add steps behind `workflow.patched` (ADR-090).
3. **Isolation:** move `parse_isolated`'s child-process runner to `kernel/isolation.py` (`run_isolated(fn, *args, timeout, cpu_seconds, memory_bytes)`), used by ledger import and extraction alike. A crash, timeout or limit hit is `unreadable` (AC-2).
4. **Extraction** (`evidence/extraction/`), pure functions run in the child:
   - **PDF** (`pdfplumber`): page text, simple tables, dates, amounts; no text layer or encrypted → `unreadable` with a reason (`scanned`, `encrypted`) (AC-3); 200 pages at most;
   - **XLSX, CSV:** cached values only (`data_only`, `read_only`, no VBA), sheet names, header and total rows; 60,000 rows (AC-4);
   - **bank statement fields** (by general labels: "Statement period", "Account number", "Beginning/Opening balance", "Ending/Closing balance", "Total deposits/credits", "Total withdrawals/debits"): account holder, last four digits, period, opening, closing, credits, debits;
   - **aging fields:** as-of date, bucket columns, row totals, grand total;
   - images and Word documents: `not_extracted`.
5. **Derived record** `upload_extractions` (migration 0043; insert-only; owner evidence): source (`evidence_version_id` or `inbox_file_id`, exactly one), `extractor_version`, status (`extracted`, `unreadable`, `not_extracted`), reason, summary fields (dates; amounts as `numeric(20,2)`; account last four; entity name, capped and `restricted`), and the full derived JSON in object storage (content-addressed, key, version, fingerprint, size). Unique per source and extractor version. Never alters the evidence (ADR-110).
6. **Worker:** add `evidence` to `MODULES` in `worker/__main__.py` (one line; evidence gains `WORKFLOWS`, `ACTIVITIES`, `SUBSCRIPTIONS` in its `api.py`).
7. **Flag** `uploads.processing` (default off, expires in 90 days or less); the seed turns it on for Dev firm.
8. **Synthetic documents** (`abacus_tools/synthetic/documents.py`): bank statement PDFs in three layouts (a tiny PDF writer with text operators, no new dependency), an image-only "scanned" PDF, a PDF with an `/Encrypt` dictionary, and aging schedules (XLSX, openpyxl) with and without formulas.
9. **Tests:** scanning on all three paths; extraction per synthetic layout; scanned, encrypted and oversized; formulas never evaluated; isolation crash and timeout; workflow replay histories; subscriber idempotency.

### Questions for the human
- **D1 — the worker.** Recommended: add `evidence` to the worker's `MODULES`, a one-line change in protected `worker/__main__.py`. Alternative: host the workflow in `connections`, the wrong owner for uploads.
- **D2 — shared isolation.** Recommended: move the child-process runner to `kernel/isolation.py` and have ledger import use it (a small refactor in `connections`). Alternative: a second copy in evidence.
- **D3 — the derived record.** Recommended: full extraction as JSON in object storage, with the fields checks need as columns. Alternative: everything in a `jsonb` column, which puts large client text in the database.
- **D4 — setup files.** Recommended: scan the firm's setup files (engagement letter, acceptance) too, since they share `checked()`; they're not processed further.
- **D5 — approval file:** `backend/src/abacus/modules/evidence/**`, `backend/src/abacus/modules/connections/**` (D2), `backend/src/abacus/worker/**` (D1), `docs/architecture/dependency-allowlist.yaml` (pdfplumber, pypdfium2 and their dependencies pdfminer.six and Pillow), `docs/architecture/feature-flags.yaml`, `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py`, `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every state change is audited
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review after SPEC-029 merged (#99).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
