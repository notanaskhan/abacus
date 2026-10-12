---
id: TASK-055
title: "Upload processing, part 2: document kinds, mechanical checks and ledger cross-checks"
spec: SPEC-029
acceptance_criteria: [AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: red
status: awaiting-approval
branch: task-055-upload-checks
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
SPEC-029 §8, TASK-055: request items say which document they expect, and every upload is checked by code against that expectation, the engagement and the ledger. Results are recorded per evidence version with an audience (client or firm) and exposed through an API. The screens are TASK-057. Builds on TASK-054 (PR #100), so this branch stacks on it.

## Scope
SPEC-029 AC-5 to AC-9; goals 4, 5 and 6; the checks API from §6.

## Context to load
- Spec: `docs/specs/SPEC-029-upload-processing.md` §4.4–4.7, §6, Q3–Q6, Q8; ADR-050, ADR-111
- Code: `requests/classification.py` (tier rules), `requests/service.py` (create, classify, the tier override); `engagements/workbook.py` (`AccountRule`, `area_for`), `engagements/service.py` (`version_detail`, `engagement_metadata`); `evidence/processing.py`, `extraction.py`, `document_fields.py`, `workflows.py` (TASK-054); `evidence/service.py` (`engagement_snapshots`); `ledger/api.py` (`snapshot_view`); `agents/graph.py` (how snapshot accounts map to areas)

## Plan
- [ ] Plan approved by human

### What the code shows
- **Classification** (`requests/classification.py`) is a fixed keyword table run on create and on reclassification. AR and AP agings are already told apart there (`ar_aging`, `ap_aging` datasets).
- **Methodology areas are the firm's own** (code and name, from its workbook). Nothing marks an area as "cash" or "receivables"; `area_for` maps account codes to area codes by ranges. An engagement may have no methodology pinned.
- **Evidence may not import ledger** (`MODULE_DEPENDENCIES["evidence"]` is identity, engagements, requests). Ledger imports nothing, so allowing evidence → ledger makes no cycle.
- **The tier override** uses `request_item.update` (partner, manager, senior).
- **The duplicate check per item** already exists at upload (`duplicate_upload`); engagement-wide duplicates aren't detected.

### Design (for founder review)
1. **Document kinds** (requests; migration 0044):
   - `request_items.document_kind` (`bank_statement`, `ar_aging`, `ap_aging`, `schedule`, or null) and `document_kind_source` (`rule`, `override`);
   - a second fixed keyword table beside the tier rules: "bank statement(s)" → `bank_statement`; AR and AP aging phrases (the existing ones) → `ar_aging` / `ap_aging`; "schedule", "reconciliation", "roll-forward" → `schedule`. Set on create and on reclassification unless overridden;
   - override: `PUT …/request-items/{id}/document-kind` (`request_item.update`), audited, with the item's kind shown in the API (AC-5).
2. **Checks** (`evidence/checks.py`, pure code, ADR-050), from the extraction's columns and JSON, the item's kind, the engagement's year end and client entity name:
   - every file: `unreadable` (extraction status, with its reason); `duplicate` (the same fingerprint on another version in this engagement, naming that item);
   - `bank_statement`: `stale_as_of` (the period ends more than 45 days before the year end); otherwise `wrong_period` (the period doesn't include the year end; with no start printed, the 31 days before the end); `wrong_entity` (the account holder and the client entity's name differ after normalisation: case, punctuation, and legal suffixes such as Inc, LLC, Ltd, Corp, Co dropped); `totals_dont_add_up` (opening + credits − debits ≠ closing, when all four are printed);
   - `ar_aging` / `ap_aging`: `wrong_period` (as-of isn't the year end); `totals_dont_add_up` (a row's buckets ≠ its total, column sums ≠ the total row, or row totals ≠ the grand total; cells without a value are skipped, never counted as zero);
   - `schedule`: `totals_dont_add_up` (a row labelled Total differs from the sum of the numbers above it in its column, back to the header or the previous total);
   - each result: outcome `passed`, `problem` or `not_applicable` (with why), audience `client` or `firm`, and code-computed values only (dates, amounts, an item reference).
3. **Ledger cross-checks** (firm audience only, Q3), against the latest snapshot behind this engagement's evidence for its year end:
   - **bank statement:** cash accounts are those in a methodology area whose name contains "cash" or "bank" (or, with no methodology pinned, accounts so named); match the statement's last four digits to an account name; else use the only cash account; else `not_applicable` ("couldn't tell which account") (Q5). Records the account code and closing balance − book balance;
   - **AR / AP aging:** control accounts named "accounts receivable" / "trade receivables" (allowances excluded), or "accounts payable" / "trade payables"; grand total − book balance (debit-normal for AR, credit-normal for AP);
   - no snapshot for the year end: `not_applicable` ("no trial balance yet").
4. **Record** `upload_checks` (evidence; migration 0044; insert-only): per evidence version and checker version, one row per check: code, outcome, audience, reason, `expected_date`, `found_date`, `amount`, `difference`, `account_code`, `ref_item_id`. Unique per version, check and checker version.
5. **Workflow v2:** `UploadProcessing` adds `upload.check` after extraction behind `workflow.patched("checks")`, for evidence versions only (inbox files are checked once assigned, Q8). A v2 history is recorded; v1 still replays.
6. **API:** `GET /v1/engagements/{id}/evidence-versions/{vid}/checks` (`evidence.read`): every check for the firm; for client roles, only `client`-audience checks on their own uploads (AC-10's rule enforced here, so screens can't leak a firm check).
7. **Tests:** document kind rules and override; every check's pass, problem and not-applicable cases on synthetic statements and agings; entity name normalisation; cross-checks with and without a methodology and a snapshot; the client filter; v2 replay.

### Questions for the human
- **D1 — aging kinds.** Recommended: split SPEC-029's `aging_schedule` into `ar_aging` and `ap_aging`, matching the existing dataset names, so the cross-check knows which control account to use. Alternative: one kind, with the side guessed from the description at check time.
- **D2 — evidence reads the ledger.** Recommended: allow evidence → ledger in `MODULE_DEPENDENCIES` (a protected file; ledger imports nothing, so no cycle). Alternative: put cross-checks in `agents`, which already reads the ledger, but they're code, not an agent.
- **D3 — finding cash and control accounts.** Recommended: by methodology area name ("cash", "bank") and account name ("accounts receivable", "accounts payable"), never guessed beyond that; `not_applicable` otherwise. A later task can let firms tag areas explicitly.
- **D4 — template carry-over.** Recommended: rules and the team override now; a "Document kind" column in methodology templates later, with the workbook format change it needs. This defers the "carried by methodology template items" part of SPEC-029 goal 4.
- **D5 — changing a kind after upload.** Recommended: checks are recorded against the kind at the time; changing the kind re-runs checks for that item's latest version (one more workflow start). Alternative: no re-run.
- **D6 — approval file:** `backend/src/abacus/modules/evidence/**`, `backend/src/abacus/modules/ledger/**` (if its API needs a lookup), `backend/src/abacus_tools/quality/banned_patterns.py` (D2), `backend/src/abacus_tools/quality/schema_check.py`, `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every state change is audited
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-12` — Design written for founder review, stacked on TASK-054 (#100).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
