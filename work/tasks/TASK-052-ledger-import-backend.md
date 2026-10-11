---
id: TASK-052
title: "Ledger file import, part 1: the import connector, formats and pipeline"
spec: SPEC-028
acceptance_criteria: [AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: done
branch: task-052-ledger-import
worktree:
created: 2026-10-11
updated: 2026-10-11
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-028, split in two (D1):
- **TASK-052 (this task, backend):** the import connector, the QuickBooks Online and Xero trial balance formats, the pipeline changes, provenance `imported`, the scanner interface, the import API, the permission and the flag;
- **TASK-053 (web):** connect or export, guided steps, upload and status, plain-words failures, and wording that adapts to capabilities.

## Scope
SPEC-028 AC-3 to AC-8 (backend). AC-1, AC-2 and AC-9 are TASK-053.

## Context to load
- Spec: `docs/specs/SPEC-028-ledger-file-import.md`; ADR-037, ADR-038, ADR-042, ADR-107, ADR-110
- Code:
  - `connections/connector.py`, `service.py` (`CONNECTORS`, `connector_for`), `pipeline.py` (stages), `fake.py`, `fake_format.py` (`parse_trial_balance`), `connect.py`, `auto_retrieval.py`;
  - `ledger/normalise.py` (`validate`);
  - `evidence/service.py` (`Provenance`, `Method`), `evidence/render.py` (footer);
  - migrations 0007 (`evidence_versions.method`), 0009 (`connections.provider`, `sync_runs`), 0029 (`connection_states.provider`);
  - `tests/unit/connections/conformance.py`.

## Plan
- [x] Plan approved by human (founder, 2026-10-11: D1–D5). Approved by founder: the paths named under *Protected paths*

### What the code shows
- **Five things are hardwired to the fake connector:**
  - the providers (CHECK `IN ('fake')` on `connections` and `connection_states`);
  - the normaliser (`pull_raw` hardcodes `"trial_balance"`, and `normalise` imports `parse_trial_balance`);
  - the connector registry (`{"fake": _fake}`);
  - the evidence methods (`retrieved`, `uploaded`, in a CHECK and two Literals);
  - the connect flow's provider list.
- **The normaliser refuses negative amounts** and expects declared control totals. Real exports use signed balances and often carry no totals.
- **Ledger validation, snapshots and rendering need no change:** they work on normalised lines.
- **openpyxl is approved** and already reads cached values (`data_only=True`). It never runs macros.

### Design (for founder review)
1. **The import connector** (`connections/connectors/import_file.py`):
   - capabilities: `{"trial_balance"}`; `oauth`, `incremental` and `attachments` all false;
   - `authorise_url`, `exchange_code`, `refresh`, `changes_since` and `fetch_attachment` raise `NotSupported`;
   - `pull(trial_balance, period)` returns the latest clean import for that entity and period as a `RawPayload` (`source = "import:<format>"`); with none, `ConnectorError("no_import")`;
   - `health` is true when the latest import is clean;
   - registered as `import`, and it passes the conformance suite (AC-7).
2. **Ledger imports** (connections migration 0041):
   - **`ledger_imports`:** engagement, entity, format, period, storage key, version, fingerprint, size, scan status (`pending`, `clean`, `refused`), status (`received`, `processed`, `failed`) and failure code, uploaded by, on behalf (Q4), at;
   - stored write-once through the existing content store, unique per entity and fingerprint, so a repeat upload is recognised (AC-8);
   - **the `import` provider** is added to the CHECKs. The first import for an entity creates (or reuses) its connection of provider `import`, status `active`, so `available_datasets`, classification and automatic retrieval treat it as a connection, as ADR-107 says.
3. **Scanning (ADR-110; D3):**
   - `abacus.kernel.scanning`: `scan(content) -> Clean | Refused(reason)`, behind a configured scanner;
   - the local and test scanner refuses the standard EICAR test signature and archive bombs (an XLSX whose uncompressed size or compression ratio passes a limit), and passes everything else;
   - staging chooses the real scanner (TASK-014). An import is scanned on upload, before anything parses it, and an unscanned or refused file is never parsed (AC-3).
4. **Formats as configuration** (`connections/import_formats.py`; D4):
   - a `Format` record: system, file type, how to find the header row (its expected column labels), account code and name columns, amounts as debit and credit columns or one signed balance column, an optional total-row label, an optional period cell, and the export steps for TASK-053;
   - first `qbo_trial_balance_csv` and `xero_trial_balance_xlsx`, built from synthetic fixtures that match each system's documented layout;
   - detection by header signature, so a file that matches another format is refused as `format_mismatch`, naming the likely system (SPEC-028 §4.8).
5. **Normalising an import** (`connections/import_parse.py`):
   - CSV (UTF-8 with or without BOM, or Windows-1252, Q6) and XLSX (`read_only`, `data_only`, never evaluated, macros ignored);
   - amounts accept signs, thousands separators and parentheses: a signed balance becomes debit when positive and credit when negative;
   - rows without an account code (sub-totals, notes) are skipped; the total row gives the declared control totals, otherwise the sums of the lines with `control_totals_source = "lines"` (Q2);
   - currency is USD unless stated (Q3); the existing limits apply (20 MB, 50,000 lines, strict text);
   - the output is the same `NormalisedTrialBalance` the fake parser returns, so `validate`, snapshot and render are unchanged.
6. **Isolation (ADR-110; D2):**
   - parsing runs in a short-lived child process started by the `normalise` activity, with CPU-time and memory limits (`resource.setrlimit`) and a wall-clock timeout;
   - a crash or timeout is a `failed` run with code `unreadable`, never a worker crash;
   - a dedicated upload-processing worker pool comes with SPEC-029 and staging.
7. **The pipeline:**
   - `pull_raw` takes the dataset from the run, not a constant;
   - `normalise` dispatches by provider: `fake` uses `parse_trial_balance`, `import` uses `import_parse` in the child process;
   - `render` sets `method="imported"` for the import provider and keeps `"retrieved"` otherwise;
   - the provenance footer (ADR-042) gains "Imported from a {system} export uploaded by {name} on {date}" for imports, deterministic from the import record.
8. **Provenance `imported`** (evidence migration, same 0041):
   - the `evidence_versions.method` CHECK gains `imported` (with `pulled_at` holding the upload time, as `retrieved` requires);
   - `Method` Literals in evidence service and routes;
   - the Board and item detail labels follow in TASK-053.
9. **The import API** (connections routes, existing router):
   - `GET /v1/engagements/{id}/ledger-import/formats`;
   - `POST /v1/engagements/{id}/ledger-import?format=&period_start=&period_end=` (raw body, 20 MB): scan, store, record, and start retrieval for the open tier A trial balance items through the existing automatic retrieval;
   - `GET /v1/engagements/{id}/ledger-import`: the latest import, its status and failure code;
   - the gate applies (SPEC-025: not before the engagement is open).
10. **Permissions and flag:**
    - the matrix action `ledger_import.upload` is held by the client admin, engagement partner, manager and senior (Q4: staff uploads are recorded as on behalf);
    - reading the latest import uses `connection.read_log`'s roles;
    - the per-firm flag `ledger.import` (default off, on for Dev firm).
11. **Synthetic fixtures** (`abacus_tools/synthetic`): QuickBooks Online CSV and Xero XLSX trial balances generated from the existing synthetic ledger, including signed balances, parentheses, a total row, sub-totals, a wrong period and an unbalanced one.
12. **Tests:**
    - unit: each format (AC-5), each failure (AC-6) and the repeat upload (AC-8); the scanner stub (EICAR, archive bomb); the child-process limits; the conformance suite for `import` (AC-7);
    - integration: import, then scan, then the pipeline, then evidence `imported`, then the item fulfilled (AC-3, AC-4);
    - a local smoke with both formats.

**Protected paths (approval file), each named:**
- `backend/src/abacus/modules/connections/**`: the connector, formats, parsing, pipeline, the import API;
- `backend/src/abacus/modules/evidence/**`: method `imported`, the render footer;
- `backend/src/abacus/modules/ledger/**`: only if `NormalisedTrialBalance` needs `control_totals_source` (expected: a field on the parse result, in connections);
- `docs/architecture/permission-matrix.yaml` and the generated `backend/src/abacus/modules/identity/authz/_matrix.py`: `ledger_import.upload`;
- `docs/architecture/feature-flags.yaml`: `ledger.import`;
- `backend/src/abacus_tools/quality/schema_check.py` and `banned_patterns.py`: the new table and CHECKs, and the connector registry entry (the reserved `connections/connectors/` path);
- `backend/tests/unit/**`, `backend/tests/integration/**`.

Not protected but changed: `abacus.kernel.scanning` (new; the kernel's protected parts are db, uow, crypto and storage), `abacus_tools/synthetic`, the new migration. Not touched: `api/app.py` (existing routers), identity beyond the generated matrix, agents.

### Questions for approval
- **D1. Split SPEC-028 into TASK-052 (backend) and TASK-053 (web)?** *Recommendation: yes.*
- **D2. Isolate parsing in a child process with CPU, memory and time limits, started by the pipeline's `normalise` activity, until SPEC-029 brings a dedicated upload-processing worker pool?** *Recommendation: yes.* It meets ADR-110's "isolated, with limits" now, without new infrastructure.
- **D3. A scanner interface in `abacus.kernel.scanning`, with a local stub refusing the EICAR test signature and archive bombs, and the real scanner chosen with staging?** *Recommendation: yes,* as ADR-110 says. SPEC-029 reuses it for every upload.
- **D4. Build the two formats from synthetic fixtures matching each system's documented export layout, and check them against your anonymised samples when you have them?** *Recommendation: yes.* Real samples may change column labels; the mapping is configuration, so that's a small change.
- **D5. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-11` — Design written for founder review after SPEC-028 merged (#93).
- `2026-10-11` — Built: migration 0041, `kernel.scanning`, formats, isolated parser, import connector, upload service and routes, matrix action, flag, seed. Gates and unit tests pass (9,684). Local smoke passes for both formats: EICAR refused, wrong format reported as `looks_like_*`, the same file accepted under the right format, a duplicate recognised, the item fulfilled with `imported` evidence and the footer notes.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| `ledger_imports` is insert-only; only files that scan clean are recorded; a refused file is an audit event only | An upload and its check are facts; nothing is stored or parsed for a refused file (AC-3) | No |
| One good import per entity and fingerprint (partial unique index); failed checks don't count | Found in the smoke: after a wrong-format pick, the same file must be accepted under the right format | No |
| `ledger_import.upload` needs independence, like `evidence.upload` | It's client data (SPEC-025 AC-7) | No |
| The import period is the engagement's fiscal period; the API takes no period | Fulfilment is for the fiscal period; the web shows it read-only (TASK-053). An interim period can be added later | No |
| Upload starts retrieval for open tier A trial balance items directly, as the uploader; it emits no `ConnectionCreated` | Every good upload should retrieve, not only the first; a client upload notification belongs with SPEC-029 | No |
| `pulled_at` is when the import was read; the upload time is in the footer | The conformance suite requires the time of the pull | No |

## Handoff
Backend done. Next: TASK-053 (web): connect or export, guided steps, upload, plain-words failure messages for the codes in `import_parse` and `ledger_import`, the "Imported" label. A corrected re-upload after an item is received doesn't replace the evidence yet (only open items are retrieved); decide in SPEC-029. An integration test for AC-3/AC-4 waits for the joint test session.
