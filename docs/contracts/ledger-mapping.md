# C9 v2 · Ledger taxonomy and account mapping

| Field | Value |
|---|---|
| Register row | C9 in `docs/contracts/README.md` (the taxonomy half; the layers half is `c09-ledger.md`) |
| Version | v2 |
| Status | stub (A-03-T03, 2026-10-30); the SPEC-316 v0 operations stay live on their paths (`c09-ledger.md`, "Taxonomy half, live v0") until A-03-T08 and T12 move AUD-31 here |
| Provider epic | A-03 |
| Consumers | AUD-31 (A-03-T12), AUD-06 `group_by=fs_line` (A-02); A-04 (FS-line totals), A-06 (mapped TB for adjusted layers), T-05 (groupings beside tax mapping), A-09 (one set per entity, the TB mapper), A-10 (FSP-02), C-01 |
| Freeze sprint | S20 (frozen Fri Aug 6, 2027) |
| Flag | `ledger.tb_mapping` (default off; DEC-137 override, expires 2027-04-28) |
| Spec | `docs/specs/SPEC-580-a03-sampling-and-tb-mapping-s20.md` (AC-16, AC-17); SPEC-316 for v0 |
| ADRs | ADR-341 (P-63), ADR-004, ADR-005, ADR-050, ADR-031 |

Code: `backend/src/abacus/modules/assurance/tb_mapping_contract.py` (routes and models),
`tb_mapping_fixtures.py` (the Granite Peak fixture); `ledger/mapping.py` computes; `ledger` has no
routes and imports nothing (Q-15).

## 1. Purpose
One structure every consumer reads: a firm's versioned grouping and FS-line taxonomy (firm
content, imported and published by a person, never code), one mapping set per trial balance of
record, each account's FS line computed by rule on read with people's edits recorded insert-only
on top (ADR-341 §5), code tallies, and the mapped trial balance by FS line and grouping.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system |
|---|---|---|---|---|
| Catalogue | `GET /v1/grouping-sets/catalogue` | `grouping_set.read` | every firm role | agent `task_scope` |
| Picker | `GET /v1/grouping-sets/{set_id}/versions/{version_no}/lines?q=` | `grouping_set.read` | every firm role | agent `task_scope` |
| Import (v0 path) | `POST /v1/grouping-sets/imports` | `grouping_set.import` | firm admin, practice leader, quality partner | **denied** |
| Publish (v0 path) | `POST /v1/grouping-sets/versions/{version_id}/publish` | `grouping_set.publish` (fresh MFA) | practice leader, quality partner | **denied**; DB `published_actor_kind = 'human'` |
| Mapping sets | `GET /v1/engagements/{eid}/mapping-sets?client_entity_id=&period_end=&label=` | `mapping_set.read` | engagement team | agent `task_scope` |
| Run / re-run | `POST /v1/engagements/{eid}/mapping-sets` (202) | `mapping_set.run` | EP, manager, senior | agent denied; **system** for the `trial_balance.version_created` subscriber only |
| Mapping set | `GET /v1/mapping-sets/{msid}?filter=needs_review\|unmatched&group_by=fs_line` | `mapping_set.read` | engagement team | agent `task_scope` |
| Run progress | `GET /v1/mapping-sets/{msid}/run` | `mapping_set.read` | engagement team | agent `task_scope` |
| Edit one account | `PUT /v1/mapping-sets/{msid}/accounts/{account_code}` `{fs_line_id, seen_version}` | `account_mapping.edit` | EP, manager, senior | **denied** |
| Confirm (L1) | `POST /v1/mapping-sets/{msid}/confirm` `{seen_hash}` | `mapping_set.confirm` | EP, manager, senior | **denied**; L1 through `review.api` |
| Mapped TB | `GET /v1/mapping-sets/{msid}/trial-balance` | `mapping_set.read` | engagement team | agent `task_scope` |
| TB view by FS line | `GET /v1/engagements/{eid}/trial-balances/{tb}?group_by=fs_line` (A-02's route; wired by T08; 409 `mapping_not_confirmed`) | `trial_balance.read` | as A-02 | denied |
| **Reserved (A-09)** | `POST /v1/mapping-sets/{msid}/accounts/{account_code}/adopt` | `account_mapping.edit` | — | not mounted; declared here only |

Client and third-party principals answer 404 on every route; support is denied every write.

## 3. Models
`GroupingSetSummaryOut`, `GroupingLinesOut` (classes Assets · Liabilities · Equity · Revenue ·
Expenses, groupings, FS lines with normal balance, the viewer's `recently_used`),
`MappingSetSummaryOut` (TB of record, entity, period end, grouping-set version, prior source, run
status, computed `status`, `MappingTalliesOut`, sign-off chips, `content_hash`), `MappingSetOut`
(`AccountMappingOut[]` with balance from the snapshot, state, method, confidence in words, "was",
`seen_version`; `GroupSubtotalOut[]` with an `off` where the source TB's summary line disagrees;
`allowed_actions`), `MappingRunOut`, `MappedTrialBalanceOut`, `TbFsLineGroupOut`. Inputs:
`MappingRunIn`, `AccountMappingEditIn`, `MappingConfirmIn`. Every field is classified (ADR-031):
account codes, names and amounts `confidential`; the taxonomy (firm content) and ids `internal`.

**Identity of an account mapping (DEC-1555).** ADR-341 §5 replaced the plan's stored
`account_mappings` rows, so an account mapping is named by `(mapping_set_id, account_code)`.

## 4. Status words (computed, never stored)
`mapping_set`: In progress · Prepared · Reviewed · Changed after sign-off (from the run, the
unmapped count and C3 sign-offs against `content_hash`). `account_mapping_state`: Needs review
(unmapped) · Rule · Edited; `suggested` and `adopted` are reserved for A-09 and no A-03 service
writes them (a test asserts it, A-03-T17).

## 5. Human-only actions
Publish, edit, confirm and every sign-off. The run is code a person (or the subscriber, as
system on behalf of the adopter) starts; it maps by rule only.

## 6. Errors
`unmapped_accounts {count}`, `content_changed`, `stale_version`, `mapping_run_in_progress`,
`mapping_not_confirmed` (409); `grouping_set_invalid`, `import_invalid` (422); with the v0 codes
in `c09-ledger.md`.

## 7. Audit and outbox events
Audit: `grouping_set.imported`, `grouping_set.published`, `mapping_set.created`,
`mapping_set.rules_applied` (counts by method; system on behalf of the starter),
`account_mapping.edited`, `mapping_set.confirmed`, `mapping_set.went_stale`, C3's
`sign_off.recorded`. Outbox: `grouping_set.published`, `mapping_set.confirmed`,
`mapping_set.went_stale`; consumed: A-02's `trial_balance.version_created`.

## 8. Stub behaviour (A-03-T03)
Client 404 → the action (engagement routes on the engagement; catalogue and picker, and mapping-
set ids until T08 gives the stub a table to resolve, the read at firm level with a non-person
refused on a write) → 404 with the flag off → the Granite Peak FY2026 fixture (mapping-set list
and run progress: 128 of 128, TB balanced 1 of 1, Prepared · CD) → 501 otherwise. The 128 rows and
BH FS groupings v1's lines are content A-03-T16 loads through the import endpoints and service
APIs; the stub never invents them.

## 9. Consumer contract tests
`backend/tests/contracts/c09_ledger/test_c09_v2_stub.py` (provider) and A-03-T22's consumer suite.

## 10. Versioning
v2 freezes Fri Aug 6, 2027. The v0 paths retire one sprint after AUD-31 moves (A-03-T12).
