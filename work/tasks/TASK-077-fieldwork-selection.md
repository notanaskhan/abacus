---
id: TASK-077
title: "Fieldwork, part 1a: materiality, the sampling module, procedure records, and journal entry testing's population and selection"
spec: SPEC-037
acceptance_criteria: [AC-1, AC-2, AC-3, AC-6]
risk_zone: red
status: done
branch: task-077-fieldwork-selection
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
SPEC-037 §7, TASK-077. An engagement can record materiality and start journal entry testing. Code builds the population from the reconciled general ledger, ties it out, and selects entries by the criteria plus a seeded random sample. Every selected entry says which rules chose it, and re-running gives the same entries.

Results, the workpaper, sign-off and the screens follow in TASK-078.

## Scope
SPEC-037 AC-1, AC-2, AC-3 and AC-6. AC-7 (screens) is in TASK-078.

## Context to load
- Spec: `docs/specs/SPEC-037-fieldwork-procedures.md`; ADR-050, ADR-116, ADR-117
- Code:
  - `ledger/gl_service.py` (`gl_snapshot_view`, `gl_entries`), `ledger/repository.py` (GL snapshot lookup by entity and period);
  - `evidence/render_gl.py` (`journal_key`, `journals`: how postings group into entries, TASK-070 D2);
  - `connections/gl_formats.py` (each format's transaction types);
  - `connections/workflows.py` (`GlImportWorkflow`: the pattern for one long activity);
  - `engagements/service.py` (`get_ref`, `check_facts`)

## Plan
- [x] Plan approved by human (founder, 2026-10-19: D1–D5 as recommended). Approved by founder: the paths named in D5

### What the code shows
- **A reconciled general ledger snapshot** holds every posting in the fiscal year: date, account, type, reference, counterparty, description, debit and credit. It's read in pages (`gl_entries`), up to about 760,000 lines locally.
- **Postings group into journal entries** by date, type and reference, or by date, type and name when there's no reference. That grouping lives in evidence's renderer today.
- **The ledger import refuses lines outside the fiscal year.** So "posted after year end" can't be a criterion until the subsequent-period import (SPEC-038).
- **Exports carry no user or "entered by" field**, so user-based criteria aren't possible from these files.
- **Transaction types differ by system.** QuickBooks has "Journal Entry", Xero has "Manual Journal", and other systems differ again. "Manual" therefore needs a per-format list.
- **`sampling` is already reserved:** an empty module with only `api.py`. `fieldwork` doesn't exist yet.

### Design (for founder review)
1. **Journal grouping moves to ledger (D1).** `journal_key` and `journals` move into `ledger/general_ledger.py`, as pure functions, and evidence's renderer imports them from there, so the workpaper and the selection always agree on what an entry is. An entry's amount is its total debits.
2. **Materiality** (fieldwork):
   - **Recording it:** `engagement_materiality` (insert-only; the newest row is current) holds overall materiality, performance materiality and the trivial threshold, plus the benchmark and percentage as text, who set it and when.
   - **API:** `GET` and `PUT /v1/engagements/{id}/materiality`, with `materiality.set` for the partner and manager.
   - **Validation:** amounts are positive, and trivial ≤ performance ≤ overall.
3. **The sampling module (ADR-117):** pure functions plus their records.
   - **Population:** `build_population(entries)` returns entries and totals. It must tie to the snapshot: total debits equal the snapshot's, and the entries' postings account for every line.
   - **Criteria,** each a pure function from an entry and the parameters to "selected or not", each with an id and version:
     - `large`: amount ≥ the selection threshold, which is performance materiality × the firm's percentage (default 100%);
     - `round`: a multiple of the round unit (default 1,000) and ≥ the trivial threshold;
     - `near_year_end`: posted within N days before year end (default 3);
     - `manual`: the type is in the format's manual list (D2);
     - `rare_account`: touches an account with fewer than N postings in the year (default 5);
     - `weekend`: posted on a Saturday or Sunday;
     - `keywords`: the description contains a word from the firm's list (defaults include "adjust", "correction", "reverse", "plug", "per", "manual", "reclass"; case-insensitive whole words).
   - **Random:** N entries from those the criteria didn't select, with a recorded seed. Python's `random.Random(seed)` samples over the entries sorted by key, named `seeded_v1` so it's re-performable.
   - **People's picks:** entry keys, each with a reason.
   - **The result:** each selected entry lists every rule that chose it.
4. **Procedure records** (fieldwork):
   - `procedures`: engagement, definition (`journal_entry_testing`) and its version, parameters as JSON with their source, status (`not_started`, `selecting`, `selected`, `failed`), and who started it;
   - `populations` (insert-only): procedure, GL snapshot, rule version, entry and line counts, totals, whether it tied, and the failure if not;
   - `selections` (insert-only; the newest is current): population, parameters, criteria versions, seed, random count, created by;
   - `selected_items` (insert-only): selection, entry key (date, type, reference, name), line numbers, amount, accounts, rules, picked-by and reason for people's picks.
5. **Running a selection (D3):**
   - **Starting it:** `POST …/procedures/{id}/select` (202) starts `ProcedureSelectWorkflow` (batch, one activity, like `GlImportWorkflow`). It refuses without materiality (AC-3) or without a reconciled snapshot for the engagement's entity and period.
   - **The activity** streams the snapshot's entries, builds and ties the population, applies the criteria, draws the random sample, and records everything in one transaction.
   - **Status:** `selected`, or `failed` with its code (`population_not_tied`, `no_ledger`).
   - **Re-running:** changing the parameters and selecting again creates a new selection. The old one is kept.
6. **Other API** (fieldwork router, flag `fieldwork.procedures`):
   - `GET …/procedures` and `POST …/procedures`, to start journal entry testing once per engagement;
   - `GET …/procedures/{id}`: parameters, status, population tie-out, the current selection's counts by rule;
   - `GET …/procedures/{id}/items`: selected entries, paged;
   - `PUT …/procedures/{id}/parameters` (`procedure.configure`: partner, manager);
   - `POST …/procedures/{id}/picks` (`procedure.run`).
7. **Permissions:**
   - `materiality.set` and `procedure.configure`: partner and manager;
   - `procedure.run`: partner, manager, senior and staff;
   - `procedure.read`: the team and the reviewer;
   - all marked `independence: required`, and clients are refused by role (AC-6).
8. **Firm defaults (Q6):** `fieldwork_settings` (one row per firm, versions): threshold percentage, round unit, window days, rare-account count, keyword list and random count. Read and changed through the API by a firm admin or practice leader (`methodology.manage`); its screen comes with TASK-078. A procedure copies the defaults into its parameters when it starts.
9. **Synthetic data:** `abacus_tools/synthetic/general_ledger.py` gains journal entries that trip each criterion, so tests and the Dev firm have something to find.
10. **Tests:**
    - property tests: each criterion selects exactly its entries; the same inputs and seed always select the same entries; the population ties to synthetic ledgers, and a broken tie stops;
    - validation of materiality and parameters;
    - the workflow's replay histories;
    - the API's roles, including clients refused;
    - a local smoke on the Dev firm's 760,000-line ledger.

### Questions for the human
- **D1 — where journal grouping lives.** Recommended: move it to ledger as pure functions, used by both the renderer and the selection, so "an entry" means one thing everywhere. This edits evidence's renderer (a protected path) only to change an import.
- **D2 — "manual" entries.** Recommended: a list of manual transaction types per export format in configuration, starting with QuickBooks Online "Journal Entry", Xero "Manual Journal", QuickBooks Desktop "General Journal", NetSuite "Journal" and Sage Intacct "GJ". A firm can add to it in its settings.
- **D3 — running selection in the background.** Recommended: a workflow, as general ledger imports do. A 760,000-line ledger takes tens of seconds to stream and group, which is too long for a request.
- **D4 — the criteria I can't do yet.** Entries after year end wait for the subsequent-period import (SPEC-038). Who entered an entry isn't in the exports, so that criterion waits for direct connections that provide it. Recommended: leave both out and name them in the workpaper's summary as not performed, with the reason.
- **D5 — approval file:**
  - `backend/src/abacus/api/app.py` (the fieldwork router), `backend/src/abacus/worker/**` (registering the workflow);
  - `backend/src/abacus/modules/ledger/**`, and `backend/src/abacus/modules/evidence/render_gl.py` (the import only);
  - `backend/pyproject.toml` (the fieldwork module in the layering contract), and `AGENTS.md` (the module map line);
  - `docs/architecture/permission-matrix.yaml` with the generated `backend/src/abacus/modules/identity/authz/_matrix.py`, and `docs/architecture/feature-flags.yaml`;
  - `backend/src/abacus_tools/quality/schema_check.py`, `backend/src/abacus_tools/quality/banned_patterns.py` (MODULE_DEPENDENCIES: fieldwork reads identity, engagements, ledger, evidence and requests);
  - `backend/tests/unit/**`, `backend/tests/integration/**`, `backend/tests/workflows/**`.
  - `fieldwork` and `sampling` themselves aren't protected paths.

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated

## Progress log
- `2026-10-19` — Design written for founder review after SPEC-037, ADR-116 and ADR-117 were approved (PR #133, awaiting merge).
- `2026-10-19` — Built (D1–D5): journal grouping moved to `ledger.general_ledger` (evidence's renderer imports it); `sampling` (population, tie-out, criteria, `seeded_v1`, people's picks); migration 0057 (materiality, firm defaults, procedures, populations, selections, selected items); the `fieldwork` module (service, routes, `ProcedureSelectWorkflow` with v1 replay histories, activities); `materiality.set`, `procedure.configure/run/read`; flag `fieldwork.procedures`; synthetic ledgers with planted test entries. Unit and workflow tests (11,165) and gates pass. Local smoke on the Dev firm's 760,072-line ledger: selection refused without materiality; invalid materiality refused; clients refused; 380,036 entries tied out; selected in 11–16 seconds; re-running gave the same entries. The first smoke showed the weekend rule alone choosing 107,678 entries: the founder chose a trivial floor (criteria v2), after which the bulk ledger's small transfers fall below it and planted entries are all chosen.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Every criterion but `large` applies only at or above the trivial threshold (criteria v2) | Founder, 2026-10-19, after the smoke: otherwise `weekend` alone selected 107,678 entries | No |
| `seeded_v1` uses only `Random.random()`, not `Random.sample` | Python guarantees `random()`'s sequence across versions, not `sample`'s, and a selection must be re-performable | No |
| Populations, selections and items are fieldwork's tables; `sampling` stays pure functions | Records belong with the procedure that owns them; sampling has nothing to store | No |
| A person's pick that names an entry no longer in the ledger lapses at the next selection | A replacement ledger can drop it; failing the whole selection would block the team | No |

## Handoff
Done. Next: TASK-078 (results, support, the workpaper renderer, sign-off, screens). Branch is built on `spec-037-fieldwork` (PR #133, awaiting merge).
