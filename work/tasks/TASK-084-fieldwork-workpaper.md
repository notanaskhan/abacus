---
id: TASK-084
title: "Fieldwork, part 1b: results and support for selected entries, the journal entry testing workpaper, sign-off, and the screens"
spec: SPEC-037
acceptance_criteria: [AC-4, AC-5, AC-6, AC-7]
risk_zone: red
status: done
branch: fieldwork-part1
worktree:
created: 2026-10-19
updated: 2026-10-19
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
SPEC-037 §7, TASK-084. After TASK-083's selection, the team works through each selected entry:
- links its support from evidence already in Abacus, or asks the client for it;
- records a result for each entry;
- writes the conclusion.

Code renders the journal entry testing workpaper. The preparer signs it ready and a different person signs it reviewed (ADR-131). All of this happens on a new Fieldwork tab.

## Scope
SPEC-037 AC-4, AC-5, AC-6 and AC-7. The AI entry assessor is TASK-085.

## Context to load
- Spec: `docs/specs/SPEC-037-fieldwork-procedures.md`; ADR-042, ADR-111, ADR-131, ADR-132
- Code:
  - `fieldwork/` (TASK-083: procedures, selections, `selected_items`);
  - `evidence/api.py` (`evidence_versions_for`), `requests/api.py` (`add_request_item`, `NewRequestItem`);
  - `evidence/render_gl.py` (streaming openpyxl, fixed metadata and ZIP timestamps);
  - `apps/web/src/screens/EngagementLayout.tsx` (tabs), `GlExport.tsx` and `TemplateGuidanceDrafts.tsx` (the patterns for status polling and states)

## Plan
- [x] Plan approved by human (founder, 2026-10-19: D1–D4 as recommended). Approved by founder: the paths named in D4

### What the code shows
- **TASK-083 records the selection.** Each selected entry has a key, line numbers, accounts, amount, descriptions and the rules that chose it. Re-selecting creates a new selection; the old one stays.
- **Evidence and requests** are reachable through their APIs:
  - evidence lists an engagement's versions under `evidence.read`;
  - requests creates an item under `request_item.create`, which the client then sees as usual;
  - fieldwork may depend on both (TASK-083's module rules).
- **Object storage belongs to evidence.** It's encrypted, Object Lock, protected. Workpapers aren't evidence.
- **Rendering can be deterministic.** `render_gl` already produces byte-identical XLSX from the same inputs (ADR-042).

### Design (for founder review)
1. **Results** (fieldwork; `item_results`, insert-only, the newest per item is current):
   - **The result:** `supported`, `exception` (a note is required) or `not_tested` (a reason is required). Each one records who and when, plus the evidence versions it relies on (`evidence_links`, checked to belong to the engagement).
   - **API:** `PUT …/procedures/{id}/items/{item}/result` (`procedure.run`).
   - **Scope:** results belong to the current selection's entries. A new selection starts with no results, and its predecessor's results stay with it.
2. **Asking the client for support:** `POST …/items/{item}/request-support` (`procedure.run`).
   - It creates a request item through `requests.add_request_item`, in the audit area "Journal entries", worded "Support for journal entry {reference} of {date}, {amount}: the approved entry and the documents behind it".
   - It links that request item to the selected entry (`item_support_requests`).
   - The client sees an ordinary request. When evidence arrives, the person links it in the entry's result.
   - The request carries only the entry's own reference, date and amount, never its description, which can be internal.
3. **Conclusion:** `PUT …/procedures/{id}/conclusion` (`procedure.run`): the preparer's text, up to 4,000 characters. It's appended like results.
4. **Workpaper versions and sign-off (ADR-131; D1):**
   - **`workpaper_versions`** (insert-only): procedure, version number, selection, the result IDs it includes, the conclusion ID, and the SHA-256 of its rendered bytes.
   - **Signing ready** (`workpaper.sign_ready`: staff, senior, manager or partner) creates the next version from the current state. It's refused unless every selected entry has a result and there's a conclusion.
   - **Signing reviewed** (`workpaper.sign_reviewed`: senior, manager or partner) applies to the latest ready version. It's refused for the preparer, and refused if anything has changed since that version.
   - **`workpaper_signatures`** (insert-only): version, kind (`ready` or `reviewed`), who and when.
   - **Changing anything after signing** (a result, the conclusion or the selection) makes the current state a draft again. Earlier versions keep their signatures.
   - **Downloading:** `GET …/procedures/{id}/workpaper?version=n`. Without a version it renders the current draft.
5. **The workpaper (ADR-131; D2):** deterministic XLSX, written by streaming openpyxl with fixed properties and ZIP timestamps. Every cell is written as text or a number, never a formula. Sheets:
   - **Summary:** engagement and year end; materiality as entered; the procedure and its version; the general ledger snapshot and the population tie-out (entries, lines, debits, credits); the criteria version, parameters, random method and seed; counts by rule; results counts; criteria not performed and why (TASK-083 D4); the conclusion;
   - **Selections:** one row per selected entry with date, type, reference, counterparty, accounts, amount, the rules that chose it, a person's reason, the result, the note, linked evidence (file name and version) and the support request;
   - **Exceptions:** only entries with exceptions, with their notes;
   - **Sign-off:** each signature, with who, the role, when and the version.

   The full population isn't repeated (D2). The journal listing workbook from TASK-070 already holds it as evidence, and the Summary names it.
6. **Screens** (web), on a new **Fieldwork** tab on the engagement:
   - **materiality:** shown, and editable by the partner or manager;
   - **journal entry testing:** "Start", then the parameters (editable by the partner or manager), "Select entries" with progress, the tie-out, and counts by rule;
   - **selected entries:** a table showing each entry's rules, result controls (supported, exception or not tested, with note), "Link evidence" (a picker of the engagement's versions), and "Ask the client for support";
   - **the conclusion box;**
   - **the workpaper panel:** current status (draft, ready or reviewed), "Sign as ready", "Sign as reviewed", download, and versions with their signatures;
   - **the states:** loading, empty ("Import the general ledger first", "Set materiality first"), error and not allowed;
   - **firm defaults:** a "Journal entry testing defaults" panel in firm admin → Methodology.
7. **Clients (AC-6):** no fieldwork route allows a client role. A test proves it, and that the support request's wording holds only reference, date and amount.
8. **Tests:**
   - deterministic bytes for the same records;
   - each sheet's contents on a small synthetic selection;
   - sign-off rules: incomplete results, the preparer reviewing their own work, review after a change, and versioning;
   - result validation, and evidence that belongs to another engagement refused;
   - support requests' wording and linking;
   - clients refused;
   - vitest for the tab's states and the result and sign-off flows;
   - a local smoke through the screens on the Dev firm.

### Questions for the human
- **D1 — keeping signed workpapers.** Recommended: store each signed version's records and the SHA-256 of its rendered bytes, and re-render on download, checking the hash. Every input is immutable, so the bytes are reproducible, and this needs no new storage. The alternative is storing each signed file in object storage. That means writing through evidence's storage, a protected path, for files that aren't evidence. I'd add it when locking at documentation completion arrives (ADR-131 Q1).
- **D2 — what the workpaper includes.** Recommended: the population as a tie-out on the Summary sheet, with each selected entry in full. The 380,000-entry population itself isn't copied, because it already exists as the journal listing evidence, which the workpaper names.
- **D3 — who signs.** As ADR-131 Q2 says: staff, senior, manager or partner sign as preparer; senior, manager or partner sign as reviewer, never the preparer. Recommended: the engagement's `reviewer` role (engagement quality reviewer) may also sign as reviewer.
- **D4 — approval file:**
  - `docs/architecture/permission-matrix.yaml` (`workpaper.sign_ready`, `workpaper.sign_reviewed`) with the generated `backend/src/abacus/modules/identity/authz/_matrix.py`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py` (list exemptions for one procedure's records);
  - `backend/tests/unit/**`, `backend/tests/integration/**`.
  - Fieldwork, the web app and the migration aren't protected paths, and the router is already registered.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-19` — Design written for founder review after TASK-083 (PR #140, awaiting merge with #133).
- `2026-10-19` — Built (D1–D4): migration 0058 (results, support requests, conclusions, workpaper versions with the pinned materiality, signatures); `workpaper.py` (deterministic renderer) and `workpapers.py` (results, support, conclusion, sign-off, download with fingerprint check); routes; `workpaper.sign_ready/sign_reviewed`; the Fieldwork tab and the firm defaults panel. Unit and workflow tests (11,263), web (350) and gates pass. Local smoke on the Dev engagement: signing before results and an exception without a note were refused; the support request carried only reference, date and amount; Sam signed ready, his own review was refused, a client was refused, Dana signed reviewed; version 1 downloaded with four sheets, re-rendered byte-identical and its fingerprint checked; a later change made it a draft again.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| A signed version pins the materiality it used (`materiality_id`) | Materiality can change after signing; re-rendering must use what was signed | No |
| The fingerprint covers the content without the Sign-off sheet | The reviewer's signature comes after the preparer's; it mustn't change what was signed | No |
| Fieldwork has its own small deterministic XLSX writer | Evidence's helpers are internal to a protected module; the duplication is about 40 lines | No |

## Handoff
Done. SPEC-037 part 1 is complete except TASK-085 (the AI entry assessor, optional). Branch builds on #140 and #133.
