---
id: SPEC-330
title: "Audits cockpit, A-01 wave 1: screen contracts, the audits family stub, record-mode phases and the cockpit L3 - outline"
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-013, ADR-018, ADR-024, ADR-031, ADR-036, ADR-139]
related_specs: [SPEC-314, SPEC-321]
created: 2026-10-24
updated: 2026-10-24
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
**Non-goals:** the index and cockpit read models (A-01-T08, T09), the C5 v1.1 projection
(A-01-T10), exports (A-01-T17 onward), release and archive records (A-01-T23), the screens
(A-01-T11, T12, T15).

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

## 6. Data
Migration `0134_assurance_profile_phase`: `assurance_work_items` + `ebp_plan_kind`,
`limited_scope_103a3c`, `phase_source`, `phase_changed_at`, `version`; new insert-only
`assurance_phase_events`. See A-01 §4.2 and the contract.

## 7. Open questions
Recorded in `docs/product/decision-log.md` DEC-260 to DEC-264.
