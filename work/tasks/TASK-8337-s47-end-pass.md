---
id: TASK-8337
title: S47 end pass — gates, suites and fixes for the S47 stack
spec: SPEC-655
acceptance_criteria: [AC-50, AC-51]
risk_zone: red
status: in-review
branch: s47-end-pass
created: 2026-11-16
updated: 2026-11-16
---

## Objective
Run the S47 end pass (AMENDMENT-solo §7; S47.md §6) once over the stacked S47 rows (#2108 to
#2152) and fix what it finds. Build first, test last.

## Plan
- Client regenerated; `make check-fast` (lint, pyright, banned patterns, docs, generated files,
  frontend tsc/eslint/build); full `tests/unit`; the new integration, golden and security files
  under the test lock (`-n 4`); one security review of the red diffs; records.
- Rollback: the end-pass PR is one commit on `w01-t17-connect-flows`; revert it alone.

## Progress log
- 2026-11-16: full unit run found 18 failures and 4 environment errors; check-fast found 19
  banned-pattern findings in S47 code and 38 document violations. Fixes (DEC-5322):
  - Boundaries (BOUND-002, OWN-001): closes registers its own C17 tools
    (`agents.api.register_declared`); `sampling.read_selected_entry` moved into assurance over
    `sampling.api.selected_entry` (it also named a wrong table, `population_records`, and was
    never imported, so never registered); a deviation's finding goes through
    `workpapers.api.register_finding_raiser`; the fieldwork mode reads
    `workpapers.api.deviation_counts`; the component scope reads its client through
    `engagements.api.client_of`; the confirmation link row takes its principal from
    `identity.api.live_principal`; the transaction question's audit owner joins request lists.
  - Lint: clock through `kernel.clock`, reasons on type ignores, a task reference on the strict
    xfail, `expansions.record_decision` (REVIEW-001), `choose_coverage` (CONN-001), the
    question's own codes (REQ-002), the 1041 gate's step constants (TAXAPPROVE-001), `subtotals`
    and `raise_question` (L12), the C-01-T48 isolation test through `tenant_session`.
  - Missing C17 description prompts for four A-08-T23 tools added
    (`tool.sampling.read_selected_entry`, `tool.ledger.counterparty_activity`,
    `tool.assurance.propose_explanation`, `tool.assurance.propose_reconciliation`).
  - G-04-T04's `tax` entitlement renamed `tax_services` (it made every `tax.*` flag illegal);
    0920 is not on main.
  - Reviewed lists updated, each with its reason: v2 specs, first tools, independent tool
    coverage, the compute contract, the sealed-name reads, `VerifiedIdentity`'s fields, the
    worker's C13 subscriptions, the 65-day election's audit owner. The drafter's "no tools"
    guarantee became "every tool reads, computes or proposes through `suggestion.create`".
  - Docs: the 37 S47 task files cite their SPEC and its AC ids (the section moved into the
    Objective); RB-90 frontmatter.
  - Security review (red diffs): the respondent's live submit now requires the path's link and
    the page credential to name one principal; WB-11's events cursor is parsed in code (a
    malformed one starts from the newest, as W-01-T15's test pins, never a database error). No other finding.
  - Integration and security run (15,200 tests, `-n 4`, under the lock): 9 failures, fixed.
    Product bugs: `closes.runs.start_run` pinned the plan and started the close before any
    check, so an agent's refused start still wrote them (INV-1, AC-28): it now refuses a
    non-human and authorises `close_run.start` first. `closes.accounts._keep` wrote schedule
    results with no audit event (and would fail on a read that changed nothing): it now
    compares first and records `arrangement.result_recorded` only when it writes.
    Test-side: C-01-T46's AC-9 and AC-18 set-ups (a started close; a second version of the one
    plan, not a second plan; the pin is once, so a repeat pin is None), C-01-T24's contact kind
    (`client_person`), C-01-T21's recorded AJE dated in its month, schema_check's reviewed
    update columns (`sample_expansions`, 0931), and the tenant-header sweep now skips console
    actions only platform staff hold (`staff_action`, as `STAFF`). G-04 AC-23 failed because
    `_TRI_MODULES` still named `tax` (fail-closed held); it names `tax_services` now.
  - Frontend: A-09-T18's connections `CoverageOut` collided with assurance's, so the generated
    client renamed both and AUD-08 lost its type; the connections models are
    `LedgerCoverageIn`/`LedgerCoverageOut` now. check-fast (backend and frontend) green; the
    rerun of the touched integration files (A-08, A-09, C-01, G-04, T-07, W-01, schema_check,
    tenant-header sweep) 328 passed, 1 strict xfail (TASK-8107).
  - Final runs: full `tests/unit` 55,574 passed; the only failures are the three
    environment-only tests below (and the four collection errors of the same cause). W-01-T15's
    own test pins "a malformed cursor starts from the newest", so the cursor fix keeps that
    contract (no 422) and only stops the database error. Web vitest 4,269 of 4,271 before the
    fixes: the status registry counts gained G-04's six objects and 19 codes (reviewed, named
    in the test); ten of the twelve unwired handoff links are wired as typed link helpers in
    `TXT-03/links.ts`, `TXT-04/links.ts` and `AUD-12/links.ts` (the TXT-01 pattern).
  - **Open (link-contract rule 1 still red on two links):** AUD-12 → AUD-11 and ADM-08 → WB-11.
    Neither AUD-11 (the sampling canvas) nor WB-11 (the integration drawer, fixture-only from
    W-01-T16) has a live host: no route or `?ov=` overlay renders them, so there is no
    `ov.AUD11`/`ov.WB11` to call. Wiring them is building those hosts (WB-11 also needs its live
    reads), a follow-up, not an end-pass fix.
  - Environment only, not code: `tests/unit/kernel/test_classification.py` needs WeasyPrint's
    `libgobject` and `tests/unit/reporting/test_a06t33_*`, `test_client_access` need the dev
    Postgres on 55432; neither is present on this machine. CI runs them.
