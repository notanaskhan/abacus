---
id: SPEC-333
title: "Trial balance and ledger connections (A-02): the TB of record, layers, ties and leadsheets on AUD-06, entity-scoped connections on POR-16, the integrations framework v1 and the write-capability registry skeleton"
status: draft
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-031, ADR-040, ADR-044, ADR-045, ADR-050, ADR-052, ADR-089, ADR-090, ADR-107, ADR-108, ADR-136, ADR-150]
related_specs: [SPEC-020, SPEC-028, SPEC-309, SPEC-310, SPEC-311, SPEC-313, SPEC-330]
created: 2026-10-25
updated: 2026-10-25
---

> **Outline.** Written with the S8 rows of A-02 (T01 to T04; TASK-1184 to TASK-1187). The epic is
> the source until this spec is final: `docs/plan/epics/A-02.md` §3 (stories), §4 (backend), §5
> (frontend), §8 (contracts). The C9 v1 contract is `docs/contracts/c09-ledger.md`; C20 v1 is
> written by A-02-T06. SPEC-309 (TB of record, first slice), SPEC-310 (tie-outs) and SPEC-311
> (adjusted layers) are already built; this spec numbers the whole epic and names, for each
> criterion, what exists and which row finishes it.

## 1. Summary
Every audit engagement gets one trial balance of record per label, adopted by a named person from
an immutable ledger snapshot (file import today, the first live ledger read from S14), shown on
AUD-06 with code-computed layers, ties and leadsheets and line provenance. Clients get POR-16,
where they alone connect, reconnect or disconnect their systems, always beside "Export instead".
The `integrations` framework and the write-capability registry let later epics add adapters
without ever creating an undeclared write.

## 2. Problem and context
SPEC-309 to SPEC-311 shipped the TB of record, its versions, annotations, leadsheets, ties and
the AJE, RJE and Final layers on an engagement tab, without a contract, a flag, the AUD-06
grammar (groups, ticks and chips, line citations, the provenance caption) or labels on the
snapshots themselves. Connections are still engagement-scoped (SPEC-020), one per entity, with no
consent record, health or catalogue, and nothing in code stops a future write path.

**Gate check (A-02 table 0.1, 2026-10-25, base origin/s7c-batch).** P-17 is repo **ADR-150**
(the plan's "ADR-136" alias), still `proposed` with accept-by 2026-11-27; it gates T12, T15 and
T16 only, so the TB half proceeds (DEC-315). DEC-70 is decided (`docs/product/decision-log.md`,
QuickBooks Online by default); `docs/product/discovery/ledger-choice.md` is written at the M3
read and does not exist yet. The C9 v1 and C20 v1 contract issues are a human step (agents open
no GitHub issues).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement partner, manager, senior, staff | Read, adopt and re-version a TB, define ties, annotate, open in Excel |
| Reviewer, EQR | Read; sign off through P-04 |
| Client Owner (`client_admin`) | Connects, reconnects, retries and disconnects the entity's systems (POR-16) |
| System | Health ticks and on-demand pulls through the existing pipeline |
| Agent | Holds none of the new actions (INV-1) |

## 4. Goals and non-goals
**Goals:** the TB of record with labelled snapshots; layers with a fail-closed adjustment slot;
ties; leadsheets; AUD-06's read model; Open in Excel; the C9 v1 and C20 v1 contracts; entity-scoped
connections, consent records, reconnect requests and health; the integrations framework v1 and a
registry that refuses every write; the first live ledger read behind `connections.live_ledger`.
**Non-goals:** the agent-built TB (A-05), live AJE and RJE amounts (A-06), grouping sets and
mapping (A-03), entity strips and consolidation (A-09), the tax hand-off (T-06), hourly sync
(C-01), any write to a client system (C-02, P-16).

## 5. User stories and acceptance criteria
Built = already on the branch base; the row named finishes the criterion.

### Story 1 · Adopt a trial balance of record (epic §3.1, §3.7)
- **AC-1** Adopting a snapshot writes one `trial_balances` row and version 1 in one unit of work, audited with the person as a human actor, and the view's provenance names them and the source. *Built (SPEC-309 AC-1); provenance facts T03, T10.*
- **AC-2** An agent context is refused `trial_balance.adopt` by the matrix, and the table's `CHECK (actor_kind = 'human')` refuses it anyway; versions are never updated or deleted (grants and, from T04, the `ledger_immutable()` trigger). *Built; second layer T04.*
- **AC-3** A snapshot of another client entity fails `snapshot_entity_mismatch` and writes nothing. *Built.*
- **AC-4** A newer snapshot of the same entity and period is listed with a code-computed count of lines changed and net change; adopting it with a reason creates v2, leaves v1 and both snapshots untouched and emits `trial_balance.version_created`. *Built except the event (T07).*

### Story 2 · Read the trial balance (§3.2)
- **AC-5** Every total, subtotal and balance comes from the server; at E0 Northwind's six funds foot to 14,895,000.00 EOY and 12,683,000.00 BOY, investments to 16,500,000.00 / 13,940,000.00 and net assets to 16,812,400.00 / 14,228,500.00. No browser code sums a column. *Fixture T03, T05; live T10.*
- **AC-6** A preparer tick carries a citation verified by `evidence` before display; an unverifiable one renders "Uncited" and the tick is not agreed (INV-2). *T10, T22.*
- **AC-7** Line chips come from P-04 `field_tick` rows and never carry an agent's initials (INV-1, INV-5). *T10, T35.*
- **AC-8** Viewer match ids come only from typed citation locators. *T09.*
- **AC-9** A walled member gets 404 with no count revealing a hidden TB (INV-3); a member without an independence confirmation is refused `independence_pending`. *Matrix built; read model T10.*

### Story 3 · Ties (§3.3)
- **AC-10** Balanced, tie and rollforward checks compute in exact `Decimal`; the loan rollforward reads 288,500.00 + 96,200.00 − 57,450.00 − 14,850.00 = 312,400.00. *Built (SPEC-310); goldens T17.*
- **AC-11** BrokerWindow EOY 1,606,560.00 reads "off 1,560.00", red ink and a flag linked to an issue; results are computed on read and never stored. *Issue link: stub T03, live T17.*
- **AC-12** An expected value without a citation is refused `citation_required`; an agent is refused `tie_out_check.define`. *Built.*
- **AC-13** A tie changed after a sign-off makes later sign-offs read "Changed after sign-off" without updating a sign-off row. *T17.*

### Story 4 · Layers and labels (§3.4)
- **AC-14** With no adjustment source registered, AJE, RJE and Final answer `layer_unavailable`, never a Final equal to Unadjusted. *Built (SPEC-309, SPEC-311).*
- **AC-15** In fixture mode at Oct 6, Final shows the AJE column, Contributions receivable 48,600.00 (AJE-1: 33,540.00 + 15,060.00) and net assets 16,861,000.00. *T05, T14.*
- **AC-16** Harlow & Pike's Interim TB in whole dollars shows "TB: Interim · 8/31/2026", one column and a "Balances to 0" tie (86,000,000). *T14.*
- **AC-17** Each layer balances or the view returns `layer_unbalanced` with the difference; label and layer words come from the status registry (`trial_balance_label`, `trial_balance_layer`). *Registry T02; engine T07.*

### Story 5 · Leadsheets (§3.5)
- **AC-18** A leadsheet shows PY · CY · Δ · Δ% in statement grammar, Δ% rounded half-even to 0.1 % by code (Investments 13,940,000 · 16,500,000 · 2,560,000 · 18.4 %). *Built (all areas); per area stub T03.*
- **AC-19** An account with no area appears under "Unassigned", never dropped. *Built.*

### Story 6 · Line agreement, review and sign-off (§3.6)
- **AC-20** *Agree to source…* writes a C4 citation and an L1 `field_tick` as the person; amounts stay locked (ADR-004). *T35.*
- **AC-21** L2 chips appear only on reviewed lines; a preparer cannot add an L2 tick on a line they prepared. *T35.*
- **AC-22** *Sign off…* opens SHL-12 for `trial_balance:<tbId>` with the current version's content hash; hidden in production until the overlay is live. *Sign-off routes built (SPEC-313); T24.*
- **AC-23** Edit changes WP ref and area only, with a required reason, through `review.api.record_value`. *Annotations built; P-04 path T35.*

### Story 7 · Open in Excel (§3.8, §11.2 Q1)
- **AC-24** Open in Excel downloads a deterministic XLSX (byte-identical on re-render) with layer columns, tick and citation text and a provenance footer; formula-like text is neutralised (ADR-052). *Stub T03; live T22.*
- **AC-25** It needs `trial_balance.export` (engagement partner, manager, senior; no wider than `run_trace.export`) with independence and a fresh second factor (`mfa_recent`, in `fresh-mfa-actions.yaml`), and is audited `trial_balance.exported`; the binder export stays the ADR-036 path (DEC-316, amended). *Matrix T02; live T22.*

### Story 8 · C9 v1 contract stub (A-02-T03)
- **AC-26** Every C9 v1 route declares exactly one matrix action. The stubs (view by layer, leadsheet by area, Open in Excel, issue link) authorise that action on the engagement first, then answer 404 with `ledger.tb_workpaper` off and 501 `not_implemented` with it on. The SPEC-309 to SPEC-311 routes stay live and ungated (DEC-314).
- **AC-27** Every field of the C9 v1 models carries a classification tag; amounts are confidential; labels and layers are C2's generated enums; no model carries a hidden count.
- **AC-28** The issue link takes a required `Idempotency-Key`, answers 201 and documents 409; Open in Excel is the only route under `trial_balance.export`; every write and the export deny agent and system.
- **AC-29** The typed fixtures (Northwind E0, derived from the seed's trial balance and the Harborline report) foot to 16,812,400.00 EOY and 14,228,500.00 BOY, balance at 17,663,450.00 and validate against the OpenAPI document.

### Story 9 · Protected bundle (A-02-T02)
- **AC-30** The generated matrix tests refuse the agent principal every new action (`trial_balance.export`, `ledger.pull`, `connection.read`, `connection.retry`, `connection.reconnect_request`); the firm-side ones are independence-marked; `connection.read` and `connection.retry` are `scope_only` for a client Owner, and `connection.read` on a client-level resource is refused to a person whose only roles are on other engagements.
- **AC-31** The registry emits `trial_balance_label` (Standard, Interim, Prior, Budget, Preliminary) and `trial_balance_layer` (Unadjusted, AJE, RJE, Final); `ledger.tb_workpaper` is boolean, default off and expires outside Sep 1 – Oct 20.

### Story 10 · TB-of-record migration (A-02-T04)
- **AC-32** `ledger_snapshots` gains `label` (default `standard`, one of the five labels) and a generated `source_kind` from an explicit list (the five import formats `import`, `fake`, anything else `other`, never `import` by prefix); a snapshot that existed before the migration reads the same after up, down and up again, and no row is updated (no row trigger fires).
- **AC-33** For `abacus_app`, `trial_balance_versions` refuses UPDATE, DELETE and a non-human actor; for every role, its trigger refuses UPDATE, DELETE and TRUNCATE. The app may supply a snapshot's `label`, never its `source_kind`.
- **AC-34** The downgrade refuses while any snapshot carries a label other than `standard`.

### Story 11 · Client connections in the portal (§3.9)
- **AC-35** POR-16 lists one card per catalogue row whose adapter is registered in this environment, with registry words (Connected · Needs reauth · Needs attention · Not connected) and "Connected by ‹person› · ‹date› · last sync ‹time›". *T06, T16.*
- **AC-36** Starting a connection needs the authorization toggle (`authorization_required` otherwise) and fresh MFA (`connection.create`, `mfa_recent`). *T16.*
- **AC-37** The consent record (copy key, version, will and won't, authorization text, person, time, hashed IP) is written once and never updated. *T13, T16.*
- **AC-38** The first-connect disclosure reads "Brightwater Hale will read your ledger" with the single scope *Read ledger*; no write copy or scope appears until P-16 (DF-19). *T18, T28.*
- **AC-39** Disconnect crypto-erases the secret, reads "Disconnected" (neutral) and keeps every received snapshot and evidence. *T16.*
- **AC-40** *Try again* runs one retry; a second click while it runs returns the same run. *T16.*
- **AC-41** A client asking for another client's entity or connection gets 404 (INV-4); a third party sees no Connections entry; firm staff cannot start a client connection. *T16, T29.*
- **AC-42** The activity reads "Connected by ‹person› (client)", "Reconnected by …", "Disconnected by …" (INV-5). *T16.*

### Story 12 · Export instead (§3.10)
- **AC-43** Every ledger card carries *Export instead* beside *Connect*; a ledger with no live adapter offers only *Export instead*, which leads to the open TB request's guided steps. Connecting is never required (ADR-108). *T18, T28.*

### Story 13 · Reconnect requests and health (§3.11)
- **AC-44** *Ask client to reconnect* writes one `reconnect_requests` row, sends one Reconnect request email from its database template in the firm's name, and adds one POR-02 to-do that clears on reconnect. *T23.*
- **AC-45** The daily health tick turns `token_expired` or `invalid_grant` into Needs reauth with one notification, other failures into Needs attention, and runs no pull on either. *T25.*

### Story 14 · First live ledger read (§3.12)
- **AC-46** An on-demand pull records a `sync_runs` row with trigger `on_demand` and a balanced snapshot AUD-06 can adopt; the prior year lands with label `prior`. *T30.*
- **AC-47** The connector issues only declared reads to declared hosts; the interception harness fails on any non-GET data call; CONN-001 still finds no write-shaped method. *T26, T32.*
- **AC-48** In production the adapter is registered but dark behind `connections.live_ledger`, fake providers are refused at boot, and the kill switch stops pulls within one minute. *T33.*

### Story 15 · Integrations framework and registry (§3.13)
- **AC-49** A catalogue row whose adapter is not registered is never listed as available. *T12.*
- **AC-50** `execute_write` is refused `write_capability_refused` and audited; a hand edit of `_capabilities.py` fails the drift test; a W1-shaped entry is refused for an attest client. *T15.*
- **AC-51** Each `integration_secrets` blob is sealed with the tenant key and the owner row id as associated data; deleting it is a crypto-erase. *T12.*

## 6. Data
- **0073 (built):** `trial_balances`, insert-only `trial_balance_versions` (human-only CHECK), insert-only `trial_balance_annotations`. **0074 (built):** `tie_out_checks`.
- **0149 (T04):** `ledger_snapshots.label` and generated `source_kind`; `ledger_immutable()` triggers on `trial_balance_versions`. A constant default and a stored generated column change no row through DML, so ADR-004's triggers never fire.
- Later: `tie_out_check_versions` (T11), `integration_catalog`, `firm_integrations`, `integration_secrets` (T12), entity-scoped `connections`, `sync_runs.trigger`, `connection_consents`, `reconnect_requests` (T13).

## 7. Interfaces
C9 v1: `docs/contracts/c09-ledger.md`. C20 v1: written by A-02-T06. Matrix: `assurance.yaml`,
`workpapers.yaml`, `connections.yaml`. Flags: `ledger.tb_workpaper` (T02);
`connections.portal_v2` and `connections.live_ledger` arrive with the code that reads them
(DEC-315).

## 8. Authorisation and tenancy
Every TB route authorises on the engagement through `authorise` (walls 404, independence),
every list goes through `visible()`; portal connection routes are `scope_only` for the client
Owner (INV-4). The agent holds none of the actions above (INV-1).

## 9. AI behaviour
N/A: no model call, prompt, tool or eval suite (epic §6).

## 10. Security, privacy and audit
Amounts and account names are confidential; secrets restricted and sealed; IPs stored only as a
hash. Snapshots and versions are immutable (ADR-004); every state change goes through the unit of
work with an audit event; payloads carry identifiers and codes only (ADR-031).

## 11. Rollout
Flags default off; `ledger.tb_workpaper` expires 2027-04-21 under DEC-137. The SPEC-309 tab
keeps working unflagged until T10 and T24 move it onto C9 v1. Rollback: flags off; migration
0149 downgrades while every label is `standard`.

## 12. Open questions
Epic §11.2 answered with its recommended options in DEC-316.
