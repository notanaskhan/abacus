# C9 · Ledger: the trial balance of record and its layers (v1, layers half)

| Field | Value |
|---|---|
| Register row | C9 in `docs/contracts/README.md` |
| Version | v1 (layers half; A-03 adds groupings, the FS-line taxonomy and mapping, frozen S20) |
| Status | stub (A-02-T03, 2026-10-25); the SPEC-309 to SPEC-311 operations are live; the view by layer and the leadsheet by area are live (A-02-T10, 2026-10-26); the issue link (A-02-T17) and Open in Excel (A-02-T22, 2026-10-27) are live; the `ledger_line` citable is registered (A-02-T22) |
| Provider epic | A-02 (A-03 for the taxonomy half) |
| Consumers | AUD-06 (A-02-T05, T09, T14, T24); A-03 (mapping), A-04 (materiality benchmark), A-05 (document-extracted TB), A-06 (adjustment source), T-05, T-06, C-01, A-10 |
| Freeze sprint | S10 (starts Mon Mar 8, 2027) |
| Flag | `ledger.tb_workpaper` (boolean, default off, expires 2027-04-21, DEC-137) on the stubbed operations only (DEC-314) |
| Spec | `docs/specs/SPEC-333-trial-balance-and-ledger-connections.md` (and SPEC-309, SPEC-310, SPEC-311) |
| ADRs | ADR-004, ADR-005, ADR-031, ADR-050, ADR-052, ADR-136, P-36 (API conventions), P-39 |

Code: `backend/src/abacus/modules/assurance/tb_contract.py` (the v1 stubs and their models),
`backend/src/abacus/modules/assurance/routes.py` (the live TB routes),
`backend/src/abacus/modules/workpapers/routes.py` (`checks_router`, the live tie-out checks),
`backend/src/abacus/modules/ledger/api.py` (the figures). Fixture:
`apps/web/src/fixtures/seed/trial-balance.ts`.

## 1. Purpose
Consumers can rely on one trial balance of record per audit work item, client entity, label and
period end, adopted by a named person from an immutable ledger snapshot and re-versioned, never
edited (ADR-004). Every figure, subtotal, layer, balance check, leadsheet, Δ% and tie result is
computed by code on the server (ADR-050) and sent as a decimal string; a screen never sums a
column. Layers are Unadjusted, AJE, RJE and Final; AJE, RJE and Final exist only once an
adjustment source registers through `ledger.api.register_adjustment_source` (A-06, C8), and
answer `layer_unavailable` before.

## 2. Who may call it
Prefix `P = /v1/engagements/{engagement_id}/trial-balances`. Every route resolves the engagement
in the tenant (404 outside it or behind a wall, with no count of hidden rows, INV-3) and then
authorises its one action (independence required for every action here). How a pending member is
refused follows DEC-270 (ADR-164 items 2-3), which supersedes SPEC-333 AC-9's wording: a **read**
answers 403 `independence_pending` only on an attest client's engagement with `g2_blocks_view` on;
adopt, define and export stay refused to a pending member on an attest client by default (DEC-551).

| Operation | Method and path | Matrix action | Roles allowed | Agent or system | State |
|---|---|---|---|---|---|
| TB list and adoptable snapshots | `GET P` | `trial_balance.read` | partner, manager, senior, staff, reviewer | denied | live (SPEC-309) |
| Adopt v1 | `POST P` `{snapshot_id, prior_snapshot_id?, label, display_unit}` (201) | `trial_balance.adopt` | partner, manager, senior, staff | **denied** (and the table CHECK) | live |
| View (v0 shape) | `GET P/{tb_id}?version=&layer=` | `trial_balance.read` | as read | denied | live |
| Candidates | `GET P/{tb_id}/candidates` | `trial_balance.read` | as read | denied | live |
| Re-version | `POST P/{tb_id}/versions` `{snapshot_id, prior_snapshot_id?, reason, seen_version}` (201; 409 `tb_version_stale`, `tb_same_snapshot`) | `trial_balance.adopt` | as adopt | **denied** | live |
| Leadsheets, every area | `GET P/{tb_id}/leadsheets?version=&layer=` | `trial_balance.read` | as read | denied | live |
| Annotations (area, WP ref) | `POST P/{tb_id}/annotations` (201) | `trial_balance.annotate` | partner, manager, senior, staff | **denied** | live |
| Tie-out checks | `GET P/{tb_id}/checks`; `POST P/{tb_id}/checks` (201); `PUT P/{tb_id}/checks/{check_id}` | `trial_balance.read`; `tie_out_check.define` | as read; partner, manager, senior, staff | **denied** for define | live (SPEC-310) |
| TB sign-offs L1 to L5 | `POST P/{tb_id}/sign-offs/{prepare,review,manager,partner,eqr}` (201) | `sign_off.*` | per level (SPEC-313) | **denied** | live (SPEC-313) |
| **View by layer** | `GET P/{tb_id}/layers/{layer}?version=` (409 `layer_unavailable`, `layer_unbalanced`) | `trial_balance.read` | as read | denied | **live** (A-02-T10, `tb_read_model.py`) |
| **Leadsheet by area** | `GET P/{tb_id}/leadsheets/{area}?layer=&version=` (404 for an area with no lines; `Unassigned` holds the unplaced accounts) | `trial_balance.read` | as read | denied | **live** (A-02-T10) |
| **Open in Excel** | `GET P/{tb_id}/export.xlsx?layer=&version=` (XLSX attachment) | `trial_balance.export` | partner, manager, senior; fresh MFA (`mfa_recent`; DEC-316, amended) | **denied** | **live** (A-02-T22, `tb_read_model.py`): the layer exactly as the view shows it (409 `layer_unavailable`, `layer_unbalanced`), byte-identical on re-render, ticks and citations as text, a provenance footer, client text written as text; audited `trial_balance.exported` with the file's SHA-256 |
| **Issue link** | `POST P/{tb_id}/checks/{check_id}/issue-link` `{issue_id, seen_version}` (`Idempotency-Key`; 201; 409) | `tie_out_check.define` | as define | **denied** | **live** (A-02-T17): set once; the same issue again answers the link, another 409 `tie_out_check_issue_linked`, an issue of another engagement 404 |

**`ledger_line` citations (A-02-T22).** Locator `{ledger_snapshot_id, account_code}`; match id
`led:<snapshot>:<account>`; `source_version` is the snapshot id. Verified only for a reader with
`trial_balance.read` on the anchor's engagement and a snapshot of that engagement's entity
(otherwise `source_not_visible`, or `source_not_found` as if absent); a value must equal the
line's net or its side, a quote must be in the account name. A re-version that adopts another
snapshot moves every citation to the replaced snapshot (`moved`, cause `ledger_snapshot:<new>`).

A stub authorises first, then answers 404 with `ledger.tb_workpaper` off and 501
`not_implemented` with it on, so no principal learns the flag state it may not use (DEC-261's
order). The live operations are not flagged (DEC-314). A-03's mapping and draft-statement routes
under the same prefix are the taxonomy half (SPEC-316).

## 3. Models
Classification (ADR-031): **C** confidential (every amount, account code and name, area, group
and total labels); everything else internal. Nothing Restricted.

- **`TbLayerViewOut`**: `trial_balance_id`, `engagement_id`, `label` (C2 `trial_balance_label`), `layer` (C2 `trial_balance_layer`), `layers_available`, `display_unit` (`cents`\|`whole_dollars`), `period_start`, `period_end`, `prior_period_end`, `version_no`, `current_version_no`, `provenance`, `groups` C, `totals` C, `balance` C, `checks`, `newer_snapshots` (the "newer TB" banner's count of adoptable newer snapshots), `allowed_actions`.
- **`TbProvenanceOut`**: `source_kind` (`import`\|`connector`\|`fake`\|`other`, the snapshot's generated column from an explicit list, migration 0149; `connector` arrives with A-02-T26), `source`, `pulled_at`, `adopted_by_user_id`, `adopted_by_name`, `adopted_at`. The caption's words are the screen's.
- **`TbGroupOut`**: `key`, `label` C, `lines` C, `boy` C, `eoy` C (server subtotals). Live grouping is one level (audit area) until A-03.
- **`TbLayerLineOut`**: `account_code` C, `account_name` C, `area` C, `wp_ref`, `boy` C (the prior snapshot's net), `eoy` C (debit minus credit), `aje` C, `rje` C, `final` C (null on Unadjusted), `adjustment_refs`, `ticks`, `citation_ids`, `flags`.
- **`TbTickOut`**: `level` (1 to 5), `kind` (`agreed`\|`reviewed`), `actor_kind` (`human`\|`agent`), `by_user_id`, `by_name`, `initials` (null on an agent's tick: outlined, "‹person› via Agent", INV-5), `at`, `citation_id`, `verified` (false renders "Uncited", INV-2).
- **`TbLineFlagOut`**: `kind` (`does_not_tie`), `check_id`, `issue_id`.
- **`TbNamedTotalOut`**: `key`, `label` C, `boy` C, `eoy` C (Total investments, Net assets).
- **`TbLayerBalanceOut`**: `layer`, `debit` C, `credit` C, `difference` C, `balanced`.
- **`TbChecksSummaryOut`**: `tie`, `off`, `pending`, `worst` (C2 `tie_out_tally`).
- **`TbLeadsheetAreaOut`**: `trial_balance_id`, `version_no`, `area` C, `unassigned`, `layer`, `display_unit`, `rows` (`TbLeadsheetRowOut`: `account_code` C, `account_name` C, `py` C, `cy` C, `change` C, `change_pct` C), `py` C, `cy` C, `change` C, `change_pct` C (half-even to 0.1).
- **`TieIssueLinkIn`** `{issue_id, seen_version}` (extra fields refused; `Idempotency-Key` replays its answer, reused for another request 422 `idempotency_key_reused`, ED-177) → **`TieIssueLinkOut`** `{check_id, issue_id, version_no, linked_by_user_id, linked_at}`.
- A tie-out check's **`citation_ids`** are **evidence citations**: ids of evidence versions of the same engagement (SPEC-310 "an evidence citation", "citations must belong to the engagement"; another engagement's answers 404), not C4 citation rows (DEC-551).
- The live operations' models are in `assurance/routes.py` (`TrialBalancesOut`, `TrialBalanceDetailOut`, `SnapshotOut`, `LeadsheetOut`, `AdoptBody`, `VersionBody`, `AnnotationsBody`) and `workpapers/routes.py` (`TieOutCheckOut`, `TieResultOut`).

## 4. Status words
`trial_balance_label` (Standard · Interim · Prior · Budget · Preliminary; the chip "TB: Interim · {date}"), `trial_balance_layer` (Unadjusted · AJE · RJE · Final), `tie_out_tally` (tie · off {amount} · Pending), from `docs/product/status-vocabulary.yaml`. Glossary: trial balance of record, TB label, layer, leadsheet, tie-out check.

## 5. Human-only actions
`trial_balance.adopt`, `trial_balance.annotate`, `trial_balance.export` and `tie_out_check.define` deny the agent (and the system for the export) at the matrix; `trial_balance_versions` refuses a non-human row by CHECK and, from migration 0149, refuses UPDATE, DELETE and TRUNCATE for every role by trigger. The agent principal holds no C9 action (INV-1).

## 6. Errors
| Status | Code | When |
|---|---|---|
| 404 | `not_found` | Engagement or TB outside the tenant or behind a wall; a stub with the flag off |
| 403 | `forbidden` / `independence_pending` | Role, agent or system; no independence confirmation |
| 422 | `snapshot_entity_mismatch` | Adopting another entity's snapshot (`error-codes.yaml`; DEC-551) |
| 409 | `trial_balance_exists`, `no_assurance_item` | A second TB for the same item, entity, label and period; no assurance work item |
| 409 | `tb_version_stale`, `tb_same_snapshot` | Re-versioning on a stale `seen_version`, or with the current snapshot |
| 409 | `layer_unavailable` | AJE, RJE or Final before an adjustment source registers |
| 409 | `layer_unbalanced` | A layer whose debits and credits differ (`facts.layer`, `facts.difference`); `ledger.api.require_balanced` (A-02-T07), called by the view-by-layer route (A-02-T10) |
| 422 | `citation_required` | An expected value without a citation (`error-codes.yaml`; DEC-551) |
| 422 | `idempotency_key_reused` | An issue link's `Idempotency-Key` reused for another request (ED-177) |
| 409 | `tie_out_check_stale`, `tie_out_check_issue_linked` | A stale check `seen_version` (edit, issue link); a check already linked to another issue (A-02-T17) |
| 501 | `not_implemented` | A stub with the flag on |

## 7. Audit and outbox events
| Event | Written when | Payload |
|---|---|---|
| `trial_balance.created` (audit) | Adopt v1 | ids, version |
| `trial_balance.version_adopted` (audit) | Adopt v1 and every re-version | ids, version (before and after on a re-version), snapshot; the reason stays in the row |
| `trial_balance.version_created` (outbox, A-02-T07, `ledger.api.TrialBalanceVersionCreated`) | A version is adopted (v1 and every re-version) | `trial_balance_id`, `engagement_id`, `version_no`, `snapshot_id`, `prior_snapshot_id`; P-04 stale detection |
| `trial_balance.exported` (audit, A-02-T22) | Open in Excel | ids, version, layer number (0 Unadjusted to 3 Final), file SHA-256 |
| `tie_out_check.defined`, `.updated`, `.issue_linked` (audit; an edit is `.updated` since ED-176); `tie_out_check.changed` (outbox, A-02-T17) | Define, edit, link | ids and version |

## 8. Example payloads
Brightwater Hale only. `northwindTbView()` in `apps/web/src/fixtures/seed/trial-balance.ts`: Northwind Robotics 401(k) Plan PY2025, Standard, Unadjusted, v1 adopted by Marcus Delaney at 10:02 AM on Sep 14, 2026; 15 lines; Total mutual funds & CITs 14,895,000.00 / 12,683,000.00; Total investments at fair value 16,500,000.00 / 13,940,000.00; Net assets available for benefits 16,812,400.00 / 14,228,500.00; debits = credits 17,663,450.00; checks tie 3. The AUD-06 a–h scenarios are A-02-T05's.

## 9. Consumer contract tests
`backend/tests/contracts/c09_ledger/test_c09_stub.py` (the provider's stub gates: one action per route, 404 and 501, classification, the registry enums, Idempotency-Key, human only); `apps/web/src/fixtures/contracts/c09-ledger.contract.test.ts` (the typed fixture foots and matches the OpenAPI document). A-02-T08 adds the consumer suites in the same two places.

## 10. Versioning
Additive changes in place. Breaking changes ship as v2 with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S10, Mon Mar 8, 2027) | — | layers half; the taxonomy half joins at S20 |

## 11. Open points
DEC-314 (the live routes stay ungated; the stubbed paths), DEC-316 (Open in Excel needs a fresh second factor, amended by the security review; staff may adopt). Before the freeze, A-02-T10 decides whether the live view moves onto `TbLayerViewOut` (and the P-36 envelope on the list) on the same paths, with the SPEC-309 tab moved in the same change.

## A-02-T10 (2026-10-26): the live view by layer and leadsheet by area

`backend/src/abacus/modules/assurance/tb_read_model.py` declares both routes on `tb_router`. Order:
`get_ref` and `authorise` (`trial_balance.read`: a wall or another firm answers 404; a team member
without an independence confirmation 403 `independence_pending`), then the flag (404 off), then
the read. Groups are the audit areas (an annotation's area, else the engagement's own methodology
account rules, read from its applied version inside the caller's tenant session on every call, no
cache; DEC-440), alphabetical with `Unassigned` last; group subtotals, the layer's balance, Δ and
Δ% are computed in exact `Decimal` (ADR-050); an unbalanced layer is 409 `layer_unbalanced`.
`totals` is empty until A-03's grouping sets name the totals (DEC-395 D1); `ticks` are empty until
P-04's field ticks reach the view (A-02-T35); `flags` mark the accounts of a check that is `off`
(`issue_id` with A-02-T17). The SPEC-309 view (`GET P/{tb_id}`) is unchanged; the AUD-06 tab reads
the C9 routes.

## Taxonomy half, live v0 (A-03; SPEC-316; TASK-345, TASK-5009, TASK-5010; notanaskhan)

These operations run today and are not flagged. C9 v2 (A-03-T03) extends them on the same paths before the S20 freeze; it does not replace them. Code: `assurance/mapping_routes.py` (routes), `assurance/mapping.py` (service) and `ledger/mapping.py` (rules and statements).

### Who may call it

| Operation | Method and path | Matrix action | Agent |
|---|---|---|---|
| Grouping-set versions | `GET /v1/grouping-sets` | `grouping_set.import` | denied |
| Import a draft (CSV) | `POST /v1/grouping-sets/imports` (201) | `grouping_set.import` | denied |
| Publish a draft | `POST /v1/grouping-sets/versions/{version_id}/publish` (201) | `grouping_set.publish` (fresh MFA) | denied |
| The mapping | `GET P/{tb_id}/mapping` | `trial_balance.read` | denied |
| Start it on a published version | `POST P/{tb_id}/mapping` (201) | `mapping_set.edit` | deny |
| Map accounts (up to 500; a null line returns the account to the rules) | `PUT P/{tb_id}/mapping/accounts` | `mapping_set.edit` | deny |
| Preparer sign-off (L1; confirms) | `POST P/{tb_id}/mapping/sign-offs/prepare` (201) | `sign_off.prepare` | deny |
| Reviewer sign-off (L2) | `POST P/{tb_id}/mapping/sign-offs/review` (201) | `sign_off.review` | deny |
| Draft statements by layer | `GET P/{tb_id}/statements?layer=` | `trial_balance.read` | denied |

`P` is `/v1/engagements/{engagement_id}/trial-balances`. Each engagement route runs `get_ref` and `authorise` on the engagement first.

### How an account is mapped (computed on read; ADR-050)

An account takes the first of these that applies:
1. A person's newest edit (`mapping_set_edits`, insert-only).
2. The FS line the same normalised code sat on in the engagement this one rolled forward from (`prior_engagement_id`), matched by FS-line key. Only keys cross from the prior year, never its figures.
3. The published version's number ranges, first rule wins.
4. Otherwise it is unmapped.

`MappingOut` carries:
- `accounts[]`, each with `method`: `manual`, `prior_year`, `number_range` or null;
- the tallies `mapped`, `unmapped`, `manual`, `prior_year` and `number_range`;
- `tb_balanced`;
- `content_hash`, the SHA-256 of the version and each account's line. A sign-off is stale when this hash moves.

Statements present each line on its normal side, from the chosen layer.

### Human-only

Publishing, mapping and both sign-offs are human-only: the matrix denies the agent. The L1 sign-off is refused with 409 `unmapped_accounts` while any account is unmapped. A successful L1 records `mapping_set.confirmed`.

### Errors

| Status | Code | When |
|---|---|---|
| 422 | `grouping_set_invalid` | The CSV doesn't parse (row problems are kept on the draft) |
| 409 | `grouping_set_has_problems` | Publishing a draft that has problems |
| 409 | `grouping_set_published` | Publishing a version already published |
| 409 | `mapping_set_exists` | Starting a second mapping on the same trial balance |
| 422 | `mapping_invalid` | An unpublished version, a foreign FS line, or no edits / more than 500 |
| 409 | `unmapped_accounts` | L1 while accounts are unmapped |

### Audit and outbox events

- **Audit:** `grouping_set.imported`, `grouping_set.published`, `mapping_set.created`, `account_mapping.edited` (`accounts`), `sign_off.recorded`, `mapping_set.confirmed` (`accounts`), `mapping_set.went_stale` (`version_no`, `unmapped`).
- **Outbox:** `mapping_set.went_stale` (`mapping_set_id`, `engagement_id`, `trial_balance_id`, `version_no`). It is emitted once per trial balance version, on `trial_balance.version_created` from version 2 on, when the mapping's newest sign-offs are on other content. Review's stale detector consumes it and tells each signer (`sign_off_stale`).

### C9 v2 will add (A-03-T03, T08, T14)

- account states including the reserved `suggested` / `adopted` (with A-09);
- `TbMappingWorkflow` with progress;
- the `group_by=fs_line` option on the TB view;
- auto-creating the set on version 1 (needs a firm-default grouping set);
- the `mapping_set_stale` C16 kind (ayushkbhatia);
- the AUD-31 screen's shapes.
