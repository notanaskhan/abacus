---
id: SPEC-330
title: "Audits cockpit, A-01 wave 1: screen contracts, the audits family stub, record-mode phases and the cockpit L3 - outline"
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-013, ADR-018, ADR-024, ADR-031, ADR-036, ADR-139]
related_specs: [SPEC-314, SPEC-321]
created: 2026-10-24
updated: 2026-10-25
---

> **Outline.** Written with the S7 rows of A-01 (T01, T02, T03, T05, T06; TASK-1100 to TASK-1104).
> The epic is the source until this spec is final: `docs/plan/epics/A-01.md` §3.1, §3.2, §3.5
> (stories), §4 (backend), §5 (frontend), §8 (contracts). The contract is
> `docs/contracts/audits-cockpit.md`; the screen contracts are `docs/screens/AUD-01.md`,
> `AUD-02.md` and `AUD-03.md`.

## 1. Summary
An audit team sees its assurance portfolio (AUD-01), opens one engagement into a cockpit whose
rail later epics extend by registration (AUD-02), and triages the PBC list beside the documents
(AUD-03). Phases move in record mode, by a named person, while Accrued computes no gate for them.

## 2. Problem and context
`assurance_work_items` carries a phase (migration 0068) that only SPEC-314's release and archive
write. There is no audits index, no cockpit projection, no way for a person to record Fieldwork,
and no EBP profile facts. The screens are built in fixture mode first, so the contract comes
first (AGENTS 15).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Every firm role | Reads the index (metadata) and the cockpit (content roles) after walls |
| Engagement partner, manager | Record a phase; edit the EBP profile |
| Engagement partner | Records an external release (A-01-T23) |
| Agent, system, support | Denied every record and profile action (INV-1) |
| Client principals | Denied every `/v1/audits` route (INV-4) |

## 4. Goals and non-goals
**Goals:** the three screen contracts; the `engagement_export` status words; the audits routes,
models, matrix rows and flag `audits.cockpit`; the registration slots; consumer tests; migration
`assurance_profile_phase` and the phase service; the cockpit L3 in `apps/web/src/domain/audits`.
Wave 2 (S8: A-01-T07 to T10) adds the Brightwater Hale assurance slice through A-01's services,
the index and cockpit read models and the C5 v1.1 request facts with the Source Documents
aggregate. **Non-goals:** exports (A-01-T17 onward), release and archive records (A-01-T23), the
screens (A-01-T11, T12, T15).

## 5. User stories and acceptance criteria
### Story 1 · Screen contracts (A-01-T01)
- **AC-1** Every artboard letter of AUD-01 (a–i), AUD-02 (a–i) and AUD-03 (a–g) is listed as built, fixture-only or deferred with its owning epic, and every designed link of the three screens names a manifest ID.
- **AC-2** The registry emits the export words (`engagement_export`: queued, packaging, ready, failed, expired, undone) beside the existing phase, archive (`audit_engagement`) and rail (`audit_section`) words.

### Story 2 · Audits family stub (A-01-T02)
- **AC-3** Every audits route in `docs/contracts/audits-cockpit.md` §2 exists with exactly one matrix action and documents 404 and 501; the record writes take an `Idempotency-Key`.
- **AC-4** With `audits.cockpit` off every audits route answers 404; with it on, a stubbed route answers 501 `not_implemented`.
- **AC-5** Phases, rail states and request words are C2's generated enums; every field carries a classification tag; no model carries a hidden-count or hidden-by-wall field (INV-3, DEC-43); no index field carries an amount or materiality.
- **AC-6** `assurance.record_phase` and `assurance.record_archive` allow the engagement partner and manager; `assurance.record_release` the engagement partner only; release and archive require `mfa_recent`; all three require independence and deny agent, system and every client role.
- **AC-7** `register_audit_section`, `register_index_tag` and `register_audit_segment` refuse a second, different registration of a key and a section without a state provider; an unregistered section is never projected.

### Story 3 · Consumer contract tests (A-01-T03)
- **AC-8** The consumer suite asserts the index envelope (tiles foot to `total`, `counts` minus the active tile), the registry codes of every status field, the absence of hidden-count fields, and the C5 v1.1 additive request-row fields as optional.

### Story 4 · Record-mode phases (A-01-T05)
- **AC-9** A person records only the next phase of the record-mode sequence: a backward move answers 409 `phase_backward`, a skipped phase 409 `phase_skip`, the current phase 409 `phase_backward`.
- **AC-10** A phase whose gate has a registered provider cannot be recorded (409 `phase_follows_gate`); it is derived from `gate.met` (mode `derived`, actor `system`).
- **AC-11** An agent or system context is refused (403), and the table refuses a `recorded` row whose actor is not human.
- **AC-12** A recorded move writes one insert-only `assurance_phase_events` row, moves the projection (`phase`, `phase_source`, `phase_changed_at`, `version`), audits `assurance.phase_recorded` and emits `assurance.phase_changed`, in one unit of work.
- **AC-13** A derived move audits `assurance.phase_derived` and emits `assurance.phase_changed`; replaying the same `gate.met` moves nothing.
- **AC-14** The EBP profile accepts plan kinds `dc`, `403b`, `db` only (no health and welfare plan), keeps the §103(a)(3)(C) label as a boolean, answers 409 `stale_version` on a stale `seen_version`, and audits `assurance.profile_updated`.

### Story 5 · Cockpit L3 (A-01-T06)
- **AC-15** The section rail renders only the rows it is given, every disc carries text, the sub-line and idle-pill grammars follow the registry, and the TPL-02 specimen still passes.

### Story 6 · The Brightwater Hale assurance slice (A-01-T07)
- **AC-16** The loaded E0 tenant's 27 assurance work items stand at Planning 7 · Fieldwork 9 · In review 6 · Ready to release 2 · Released 3, and every phase past Planning was reached through `assurance_phase_events` written by A-01's services, one step per event: Fieldwork and In review recorded by the engagement partner, Ready to release and Released derived with their gate named; the loader writes no phase.
- **AC-17** The EBP profile facts are set through the profile service: 12 defined-contribution and 2 403(b) plans, Northwind's §103(a)(3)(C) label, each audited `assurance.profile_updated`.

### Story 7 · The AUD-01 index (A-01-T08)
- **AC-18** `GET /v1/audits` foots: with no tile pressed the phase tiles (`counts`) sum to `total` (E0: 27 = 7 + 9 + 6 + 2 + 3); a pressed tile filters the rows and every tile keeps its count; segments count the base without the segment (E0: FS 6 · EBP 14 · Review & compilation 7, no SOC & IT or Internal audit without the entitlement); the caption reads EBP 14 · FS audit 6 · Review 4 · Compilation/preparation 3.
- **AC-19** A walled audit is absent from rows, tiles, segments, caption and facets, the totals foot without it, its cockpit answers 404, and no field counts it; the keyset cursor walks every row once.
- **AC-20** PBC reads received of asked client-visible requests of published PBC binders and is null without one (Fairhaven before G3); report due is the work item's due date with its tone on `kernel.clock` (DEC-263); a released row's archive clock counts 60 days from its release (Bayside "Archive in 13 days" at E0); archived rows group under Released.
- **AC-21** A metadata-only reader (firm admin) sees every `metadata` tag and no `content` tag; a client principal, an agent or the system is refused before anything is read.

### Story 8 · The cockpit (A-01-T09)
- **AC-22** The rail holds only registered sections: a later epic registers a row (A-02's Trial Balance) without editing A-01, and a provider that answers `None` or fails leaves its row out.
- **AC-23** A-01's Overview rows read Client, Methodology (hidden without a pinned version), Standards set (hidden until it has a name), Source Documents "n of N received", Team in role order ("MO · TW · HL · MD · AC") and Activity; A-01's tags are Letter sent, EQR (from In review) and No report; "Started …" and "Processing" appear only from a registered C6 v1 engagement-run provider.
- **AC-24** A metadata-only reader gets the audit bar and overview only (no bands, dock or actions); an archived work item reads `read_only_reason: archived` with no actions.

### Story 9 · C5 v1.1 request facts and Source Documents (A-01-T10)
- **AC-25** P-06's binder request rows carry `owed_by` (an open delegation's contact as `third_party`, else the client assignee as `client_contact`, open requests only), `latest_upload` (the newest live fulfilment: label, date, channel), `match_confidence` (the matcher's shown pick for that request) and `linked_count` for the firm; a client principal's rows never carry the first three.
- **AC-26** The Source Documents aggregate groups the work item's asked PBC requests by category in binder and category order with "n of N" that foot to its totals; Missing first orders needs review, requested, received; `q` narrows rows, never totals.
- **AC-27** `requests.api.pbc_counts` answers only for work items with a published PBC binder, filtered by `visible(engagement.read_metadata)`.

## 6. Data
Migration `0134_assurance_profile_phase`: `assurance_work_items` + `ebp_plan_kind`,
`limited_scope_103a3c`, `phase_source`, `phase_changed_at`, `version`; new insert-only
`assurance_phase_events`. See A-01 §4.2 and the contract.

## 7. Open questions
Recorded in `docs/product/decision-log.md` DEC-260 to DEC-264 and DEC-310 to DEC-313.
