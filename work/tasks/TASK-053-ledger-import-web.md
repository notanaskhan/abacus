---
id: TASK-053
title: "Ledger file import, part 2: connect or export, guided steps and upload (web)"
spec: SPEC-028
acceptance_criteria: [AC-1, AC-2, AC-6, AC-9]
risk_zone: amber
status: done
branch: task-053-ledger-import-web
worktree:
created: 2026-10-11
updated: 2026-10-31
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
The web half of SPEC-028 (TASK-052 D1): the client chooses **Connect (fastest)** or **Export instead**, follows their system's steps, uploads the file, and sees at once whether it worked, in plain words. Firm screens label imported evidence.

## Scope
SPEC-028 AC-1, AC-2, AC-6 (the messages), AC-9; goals 5 (labels), 7, 8 and 9.

## Context to load
- Spec: `docs/specs/SPEC-028-ledger-file-import.md` §4.5–§4.9, §5; ADR-108, ADR-111
- Code: `apps/web/src/screens/ConnectionPanel.tsx`, `ClientEngagement.tsx`, `Overview.tsx`, `ItemDetail.tsx` (method labels), `Board.tsx` (method filter); `connections/routes.py` (import routes); `connections/import_parse.py`, `ledger/normalise.py` (failure codes)

## Plan
- [x] Plan approved by human (founder, 2026-10-12: D1–D4 as recommended). Approved by founder: the paths named under *Questions for the human* D4

### What the code shows
- `ConnectionPanel` serves the client admin (connect) and the firm (check, revoke, log). With no connection it shows only "Connect".
- The backend (TASK-052) gives `GET …/connection/import/formats` (systems, file type, steps), `POST …/connection/import?format=` (raw body; 201 with `status` and `failure_code`; 422 `file_refused`, `payload_too_large`, `empty_file`; 409 `already_connected`, `ledger_import_off`) and `GET …/connection/import` (the latest).
- Failures carry a **code only**. SPEC-028 §4.8's two richest messages need values: the unbalanced difference ("differ by $1,250.00") and the period the file covers ("covers 1 Jan–30 Nov 2026").
- Item detail and the Board already know three methods; only `retrieved` and `uploaded` have labels.

### Design (for founder review)
1. **Connect or export** (`ConnectionPanel`, client admin, no live non-import connection): two cards side by side (stacked on phones): **Connect (fastest)**, today's consent dialog unchanged; **Export instead**, opening the export flow. Hidden when the `ledger.import` flag is off (the formats call answers 409; the panel then shows Connect only).
2. **Export flow** (`LedgerExport.tsx`, new):
   - pick the system (radio cards from `formats`), then its numbered steps and expected file type;
   - the period, read-only, from the engagement's fiscal year ("Year ending 31 Dec 2026") (TASK-052 decision: the API takes no period);
   - a file input (`.csv` or `.xlsx` by format, 20 MB checked before sending), then **Upload**; a spinner while it's scanned and checked.
3. **Result, at once** (ADR-111, fixed templates in `importMessages.ts`):
   - received: "Received. We're preparing your trial balance." The item turns Received when the pipeline finishes (the panel polls the item list as today);
   - duplicate: "You've already uploaded this file. Nothing has changed.";
   - failures, one template per code: `unbalanced`, `period_mismatch`, `looks_like_qbo` / `looks_like_xero` (names both systems), `unrecognised_format`, `unreadable`, `invalid_amount`, `malformed_payload`, `unsupported_currency`, `control_totals_mismatch`, `duplicate_account`, `empty`, `payload_too_large`, `empty_file`, `file_refused` ("We couldn't accept this file. Please export it again from {system}."), `already_connected`; anything else falls back to "We couldn't read this file."
4. **After an import:** the panel shows the latest import's system, period, status and date, with **Upload a newer export**. The firm's view (`Overview`, `canConnect={false}`) shows the same summary read-only, including the failure message (AC-6, "the firm sees the same reason").
5. **Labels:** "Imported" beside "Retrieved" and "Uploaded" in item detail ("Imported from a {system} export") and the Board's method filter. A client's trial balance item met by an import reads "Provided by your export of {date}" (goal 9).
6. **States** (AC-9): loading skeletons, empty (no import yet), error alerts, not-allowed (hidden); colours from tokens only.
7. **Tests:** vitest for the two options, the steps per system, upload success, duplicate, each failure template, the flag-off fallback and the firm's read-only summary; `make generate` already ran in TASK-052.

### Questions for the human
- **D1 — values in the two richest messages.** Recommended: a small backend addition so the upload result carries `difference` (unbalanced) and `found_period_end` (wrong period), computed by code, shown through the fixed templates. It touches `connections/**` and `ledger/**` (protected; approval file below). Alternative: code-only messages now ("Debits and credits don't balance"), values later.
- **D2 — period.** Recommended: read-only fiscal year now (matches the backend). Alternative: an editable period, which needs the backend to accept one and the pipeline to fulfil only the fiscal-period item.
- **D3 — who sees Export.** Recommended: the client admin, and the firm's partner, manager and senior "on behalf" from the firm's Overview (the API already allows them, SPEC-028 Q4). Alternative: client admin only in this task.
- **D4 — approval file** for D1: `backend/src/abacus/modules/connections/**`, `backend/src/abacus/modules/ledger/**`, `backend/tests/unit/**`.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every new screen has loading, empty, error and not-allowed states; colours from tokens only
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-11` — Design written for founder review after TASK-052 merged (#95).
- `2026-10-12` — Built (D1–D4 as recommended): migration 0042 (`difference`, `found_period_end`), `check_export`, `importMessages.ts`, `LedgerExport.tsx`, connect or export in `ConnectionPanel`, the firm's read-only summary with "Upload an export for the client", "Imported" in item detail and the Board filter, "Provided by your export of …" on the client's trial balance item. Web 233 tests and backend unit tests pass; gates pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The period line reads "as of {date}", not "covers {start}–{end}" | Exports name only the period end | No |
| `mockApi` keeps a non-JSON request body as text | The upload test checks the raw file is sent | No |
| "Screen now" stays for retrieved evidence only | Unchanged scope; imported evidence is screened by the agent as before | No |

## Handoff
Done. Next under SPEC-028: NetSuite, Sage Intacct and QuickBooks Desktop formats (Q1); a corrected re-upload after an item is received (SPEC-029).

## Superseded (A-02-T38, 2026-10-31)
Closed as superseded by A-02: POR-16 replaces this connection panel (every ledger card offers *Export instead*, ADR-108). The panel and its guided export steps stay in `apps/web/src/legacy/` (`ConnectionPanel.tsx`, `LedgerExport.tsx`) until they are retired through `ac-test-integrity`; R-01's POR-04 may restyle the steps.
