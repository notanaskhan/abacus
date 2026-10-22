---
id: TASK-355
title: "F-03-T10, Q-01-T13 and Q-01-T22 · Status YAML conformance tests, platform-ops contract stub, ADR drafts P-65 and P-66"
spec: SPEC-050
acceptance_criteria: [AC-21, AC-30]
risk_zone: red
status: in-review
epic: F-03, Q-01
plan_key: F-03-T10, Q-01-T13, Q-01-T22
branch: worktree-agent-aa128e27f299be405
worktree: agent-aa128e27f299be405
created: 2026-10-22
updated: 2026-10-22
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals (`docs/plan/AMENDMENT-solo.md`). The ADR-078 split of test author and builder is void as process; the rule it served is kept: expectations come from the sources, not from the code under test.
> - Documents and tests only. No product code, no generated file, no migration, no AWS call. The repository is public: no account ID, real ARN, price, contract text, real firm or person name, counsel advice, or SSN- or EIN-shaped digits anywhere.
> - No push, no CI. Three commits, one per plan row.

## Objective

1. **F-03-T10 (SPEC-306 AC-2).** Conformance tests for `docs/product/status-vocabulary.yaml`, written from blueprint 3.3.1, addendum 3.2, gap analysis 6.5 and the handoff's `lib/status.js`.
2. **Q-01-T13 (SPEC-050 AC-21).** `docs/contracts/platform-ops.md` v1, interfaces only, registered in `docs/contracts/README.md`.
3. **Q-01-T22 (SPEC-050 AC-30).** ADR drafts for P-65 (tenant key provisioning) and P-66 (platform controls and kill switches).

## Scope

**In**
- `backend/tests/acceptance/test_f03_status_vocabulary.py` (new; `tests/acceptance` is already in `UNIT_TESTS`).
- `docs/contracts/platform-ops.md` (new), `docs/contracts/README.md` (new "Platform interfaces" table).
- `docs/adr/ADR-156-tenant-key-provisioning.md`, `docs/adr/ADR-157-platform-controls-kill-switches.md`, `docs/adr/README.md` index rows, `docs/adr/backlog.md` rows for P-65 and P-66.

**Out**
- Any fix to the YAML. Where it disagrees with a source the test stays and is `xfail(strict=True)`; the builder decides the fix.
- Filing the GitHub issues the xfail reasons cite (`#ISSUE` is a placeholder).
- Code for any interface in the contract (WorkOS port, runtime config, deploy lock, ops tasks, workflow, `control_active`, SES identity port): Q-01-T17, T18, T23, T36, T37, T45, T47.
- Accepting the two ADRs (due Fri 2026-11-27).

## How the status tests are built

- The sources are restated in the test module as data and were checked against the originals: `STATUS_JS` equals the `MAP` of `lib/status.js` (loaded under node: 21 objects, 144 words); `TABLE` restates 3.3.1 and addendum 3.2 as `display label | pill variant` per state, with `disc` where the source gives only a disc or glyph and `any` where it names no variant.
- Nothing in the YAML builds an expectation. The YAML is read only as the thing under test.
- Tests: every source object exists; every source state has its display label and, where the source names one, its pill variant (and no invented variant where it names only a disc); client words are carried; words the sources call derived are derived and never in `_statuses.STORED`; no `match` or unknown variant; every label is sentence case; the YAML lists exactly the 144 words; each word maps to a real code or has a reason; a word that is also a label on its 3.3.1 object maps there; every OpenAPI `status`, `*_status` and `state` field is an enum, only uses literals the YAML has, and (for fields whose object the sources name) only codes of that object.
- Mutation check: six one-line edits to the YAML (a title-case label, a stored Overdue, a drifted variant, a remapped word, a dropped word, a dangling code) each failed the suite; the file was restored.

## Findings (sources against the YAML and the API)

All are `xfail(strict=True)` with `TASK-355 #ISSUE` in the reason (SKIP-001 wants a real number; see the open item).

| Test | Source says | YAML or API has |
|---|---|---|
| `tie_out_tally::Reconciled ✓` | 3.3.1 displays "Reconciled ✓" | `tie_out_tally.reconciled` is "Reconciled" (`request.received` keeps its "Received ✓") |
| `test_every_openapi_status_literal_has_a_yaml_entry` (11 fields) | every status literal has a YAML entry | no entry for: AdjustmentOut `client_accepted`, `client_declined`; GlImportOut `waiting_for_tb`; KnowledgeDocumentOut `ready`, `stale`; LetterIn `not_required_this_year`; LogEntryOut and RetrievalOut `failed_validation`; MaterialityVersionOut `decided`; MatrixRowOut `needs_sign_off`, `open_notes`; SupportSessionOut `ended`; WallOut `removed`; WorkpaperOut `ready` |
| `test_an_openapi_status_field_uses_only_codes_of_its_own_object` (3 fields) | codes of Proposed entry, Integration and Audit section | AdjustmentOut (above), ConnectionOut `active` (the retired `connection.active`, now `integration.connected`), WorkpaperOut `draft`, `ready` |
| `test_every_openapi_status_field_is_an_enum` (6 fields) | a status literal can be checked | bare strings: FileMatchOut, GraphEngagementOut, GraphItemOut, LetterOut, ProcedureOut, ReviewOut |

Observations that are not failures: the handoff-word mapping has no violation of the identity rule (a word that is a label on its 3.3.1 object maps there); `FlowStepOut.state`, `SetupStepOut.state` and `CompleteIn.state` are excluded as not object statuses, with reasons in `NOT_A_STATUS`; labels are sentence case throughout.

## Platform-ops contract and the two ADRs

- The contract follows `_TEMPLATE.md`, with sections 2 and 3 adapted because most interfaces are Python ports, a static file and commands rather than routes. Every signature is typed. It is registered in a new "Platform interfaces (unnumbered)" table in `docs/contracts/README.md`, since Q-01 provides none of C1 to C21. Status `stub`; freeze planned with Q-01-T57 (S5, 2026-12-28).
- ADR numbers: next free on disk and in the other worktrees was 156. **ADR-156** is P-65, **ADR-157** is P-66; both `proposed`, red, dated 2026-10-22. `docs/adr/backlog.md` now carries the numbers and `proposed`.

## Definition of done

- [x] `backend/tests/acceptance/test_f03_status_vocabulary.py`: 714 passed, 21 xfailed (strict).
- [x] ruff, ruff format and pyright (strict) clean on the new test file.
- [x] `validate_docs` and `secrets_scan` clean after each commit.
- [x] `make check-fast`: passes with the issue placeholders swapped for a number; with `#ISSUE` in place only SKIP-001 fails (four findings).

## New dependencies

None.

## Progress log

- `2026-10-22` F-03-T10: tests written and run; mutation-checked; committed. 735 test cases (714 pass, 21 strict xfail).
- `2026-10-22` Q-01-T13: contract written and registered; committed.
- `2026-10-22` Q-01-T22: ADR-156 and ADR-157 drafted, indexed and entered in the backlog; the contract's kill-switch open points aligned with ADR-157; committed.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|
| Test file lives in `backend/tests/acceptance/` | It is where ADR-078 tests live (TASK-352); already in `UNIT_TESTS` | no |
| Findings are strict xfails citing `TASK-355 #ISSUE` | The brief: no issues filed from here; SKIP-001 needs a number, so the main session replaces the placeholder | no |
| ADR-157 proposes one spelling, `portal_sign_in`, for the stored value and the reader | The plan stores `portal_sign_in_disabled` and reads `portal_sign_in`; the T19 migration is not written yet, so one name costs nothing now | ADR-157 itself |
| ADR-157 proposes fail closed for `ai_pause` and `read_only` when the control state cannot be read, last known value for the rest | The plan is silent; a stop that quietly turns off in an outage is the worse failure for these two | ADR-157 itself |
| ADR-156 reads dual control as a merged ops-request record plus the 30-day deletion window with an alarm, until a second person with production access exists | ADR-035 requires dual control; the solo amendment voids the second person | ADR-156 itself |

## Gotchas and discoveries

- SKIP-001's pattern is `#\d+`, so `#ISSUE` fails `banned_patterns` until the real numbers are in. That is expected: with the placeholder swapped for a number, `make check-fast` passes (run on 2026-10-22 after `pnpm install` and `pnpm -C packages/api-client build:types`), and with it in place SKIP-001 reports exactly four findings, one per mark.
- Matching a source state to the YAML by display label (including context labels) and not by code name keeps the tests independent of the YAML's code naming (for example Degraded is `needs_attention`).

## Questions for the human

- [ ] File the GitHub issues for the findings above (grouped: one for the "Reconciled ✓" label, one for the 11 API status fields with no YAML entry, one for `ConnectionOut.status` using a retired code, one for the six untyped status fields), then replace `#ISSUE` in the four `FINDING_*` marks of `backend/tests/acceptance/test_f03_status_vocabulary.py`.
- [ ] Confirm or change the three proposals in "Decisions" when accepting ADR-156 and ADR-157.

## Handoff

Replace `#ISSUE` in the four `FINDING_*` marks of the test file (SKIP-001 reads each reason as a literal, so there is one per finding group), run `make check-fast`, then decide each finding: add the YAML entries or change the API fields. Accept ADR-156 and ADR-157 by Fri 2026-11-27.
