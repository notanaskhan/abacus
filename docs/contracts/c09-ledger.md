# C9 · Ledger: the trial balance of record and its layers (v1, layers half)

| Field | Value |
|---|---|
| Register row | C9 in `docs/contracts/README.md` |
| Version | v1 (layers half; A-03 adds groupings, the FS-line taxonomy and mapping, frozen S20) |
| Status | stub (A-02-T03, 2026-10-25); the SPEC-309 to SPEC-311 operations are live |
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
authorises its one action (independence required for every action here).

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
| **View by layer** | `GET P/{tb_id}/layers/{layer}?version=` (409 `layer_unavailable`, `layer_unbalanced`) | `trial_balance.read` | as read | denied | **stub** → A-02-T10 |
| **Leadsheet by area** | `GET P/{tb_id}/leadsheets/{area}?layer=&version=` | `trial_balance.read` | as read | denied | **stub** → A-02-T10 |
| **Open in Excel** | `GET P/{tb_id}/export.xlsx?layer=&version=` (XLSX attachment) | `trial_balance.export` | partner, manager, senior; fresh MFA (`mfa_recent`; DEC-316, amended) | **denied** | **stub** → A-02-T22 |
| **Issue link** | `POST P/{tb_id}/checks/{check_id}/issue-link` `{issue_id, seen_version}` (`Idempotency-Key`; 201; 409) | `tie_out_check.define` | as define | **denied** | **stub** → A-02-T17 |

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
- **`TieIssueLinkIn`** `{issue_id, seen_version}` (extra fields refused) → **`TieIssueLinkOut`** `{check_id, issue_id, version_no, linked_by_user_id, linked_at}`.
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
| 409 | `snapshot_entity_mismatch` | Adopting another entity's snapshot |
| 409 | `trial_balance_exists`, `no_assurance_item` | A second TB for the same item, entity, label and period; no assurance work item |
| 409 | `tb_version_stale`, `tb_same_snapshot` | Re-versioning on a stale `seen_version`, or with the current snapshot |
| 409 | `layer_unavailable` | AJE, RJE or Final before an adjustment source registers |
| 409 | `layer_unbalanced` | A layer whose debits and credits differ (with the difference); registered with A-02-T07 |
| 409 | `citation_required`, `tie_out_check_stale` | An expected value without a citation; a stale check `seen_version` (edit, issue link) |
| 501 | `not_implemented` | A stub with the flag on |

## 7. Audit and outbox events
| Event | Written when | Payload |
|---|---|---|
| `trial_balance.created`, `trial_balance.version_adopted` (audit) | Adopt and re-version | ids, version, label; the reason stays in the row |
| `trial_balance.version_created` (outbox, A-02-T07) | A version is adopted | ids and version; P-04 stale detection |
| `trial_balance.exported` (audit, A-02-T22) | Open in Excel | ids, version, layer |
| `tie_out_check.defined`, `.updated`, `.issue_linked` (audit); `tie_out_check.changed` (outbox, A-02-T17) | Define, edit, link | ids and version |

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
