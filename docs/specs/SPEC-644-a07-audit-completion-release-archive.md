---
id: SPEC-644
title: A-07 audit completion, release and archive — EQR (G6), completion, letters (G7), report builder, release (G8), assembly and sealed archive (G9), and DB immutability after lock
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-016, ADR-032, ADR-033, ADR-036, ADR-042, ADR-050, ADR-066, ADR-078, ADR-089, ADR-090, ADR-111]  # plan decisions P-04, P-07, P-09, P-10, P-14, P-19, P-25, P-26, P-29, P-35, P-43, P-47 in the body
related_specs: [SPEC-301, SPEC-313, SPEC-314, SPEC-642]
created: 2026-11-04
updated: 2026-11-11
---

> **Instructions for coding agents**
> - A-07's own SPEC (A-07 kickoff, S27). The Given/When/Then text of each feature is A-07 §3
>   (`docs/plan/epics/A-07.md`, F1–F11); the ACs below are the task acceptance lines of
>   `docs/plan/epics/A-07.tasks.csv`, numbered in task order (AC-n = A-07-Tnn).
> - It supersedes SPEC-314 (record mode, TASK-332) as the plan of record for A-07 and keeps every
>   SPEC-314 route working until A-07-T33 retires them behind the flags (§3).
> - Contract: `docs/contracts/audit-completion.md` v1 (module interface; no C-id, A-07 §8.1).
>   Consumed unchanged: C1, C2, C3, C4, C5, C6, C7, C8, C10, C11, C13, C16, C18, C21.
> - Agents propose, humans decide: concurrence, approvals, sends, the opinion, going concern,
>   release, lock and post-lock additions are five-layer human-only (A-07 §3, chapter 03 §4.7).
>   A-07 makes **zero model calls**; every agent step is code on the v1 recording path.

## 1. Summary
A-07 lets an audit team finish an engagement inside Accrued, from the engagement quality review
to a sealed, immutable archive (chapter 03 §3.13 and §9.6; chapter 06 §6.5; DEC-83; DEC-71):

1. **G6** EQR concurrence over a code-built digest of the partner's decided judgments (SQMS 2).
2. **Completion**: a projected checklist that names what blocks the report; subsequent events
   through the report date; legal letters; going concern as an EP decision card.
3. **G7** a representation letter composed from firm templates (database rows) and the findings,
   approved by the EP, e-signed through C7 and dated as of the report date (AU-C 580).
4. **Governance communications** (AU-C 260 planning and completion, AU-C 265/703) approved and
   sent by the EP to those charged with governance, acknowledged, with the 60-day clock.
5. **The report** from structured choices and template blocks, approved as an L4 sign-off.
6. **G8 release**: one EP-only transaction (Idempotency-Key, fresh MFA, approval grant) that
   re-checks G5–G7 at the server, renders the final report through C11, records
   `report_releases`, publishes through C10 and starts the AU-C 230 and AU-C 265 clocks.
7. **G9** a 60-day assembly countdown, a nine-item checklist, a binder index and a lock that
   seals the binder into a COMPLIANCE-mode manifest; `archived_guard()` makes the locked work
   item immutable except under the enumerated `archived_write` kinds (ADR P-43).

Every route lives under `/v1/audits/{work_item_id}` (the assurance work item, A-01) and answers
501 until A-07-T33's flags (`audits.completion`, `audits.letters`, `audits.report_release`,
`audits.archive`) are created on the Thu Jan 27, 2028 train; then 404 for a firm with the flag
off. Providers, subscribers and workflows stay dark unless the firm's
`assurance_release_mode = in_app` **and** `assurance/completion/_dark.py COMPLETION_LIVE` is true.

## 2. Decisions taken at kickoff (2026-11-04; DEC-2260, DEC-2261)
- **ADR delta check.** P-43, P-14, P-07, P-19, P-26 and P-10 are accepted in chapter 09 and
  carried in the repo (ADR-140 record mode; ADR-147 roles; ADR-342 DocuSeal for P-26's
  provider). No A-07 task needs a new ADR in S27. DEC-83 and DEC-71 stand as written.
- **OQ-1 (release and DEC-24's hold): no hold, no Undo.** The release grant is issued with
  `not_before = now`; the attestation dialog with fresh MFA is the single confirmation. A
  clarification of P-35, recorded as DEC-2260.
- **OQ-4 (reissue on an archived work item):** under the `post_issuance` exception kind owned by
  Q-05; A-07 ships only the schema hooks (`audit_report_versions.reissue_of_release_id`,
  `report_releases.kind = reissue`, `archive_additions.post_issuance_event_id`) and AUD-23 g as
  fixture-only. A note on P-43, DEC-2260.
- **The record-mode slice (SPEC-314, TASK-332) is the base, not a competitor (DEC-2261).**
  - Routes: SPEC-314's `/v1/engagements/{id}/completion/*` stay live until A-07-T33 swaps each
    screen to its `/v1/audits/{work_item_id}/*` route; T33 retires them.
  - Actions: A-07 reuses SPEC-314's names (`completion.read`, `eqr.concur`, `report.release`,
    `archive.lock`) and widens their cells (`eqr_reviewer` beside `reviewer`, A-07 §4.4); the
    new conditions (`mfa_recent`, `function_in(eqr)`, `gates_met`, the release-mode setting)
    attach when the live handlers land so the record-mode routes keep their behaviour.
  - Tables: where A-07 §4.2 names a 0077 table (`eqr_concurrences`, `archives`), A-07's
    migrations extend it with nullable work-item columns and CHECKs that bind only v2 rows;
    0077's `releases` and `completion_records` stay record-mode history and v2 writes
    `report_releases` and the letter and report tables. No migration on main is edited.
  - SPEC-314's going-concern choice (`completion.decide`) becomes the `going_concern` C3 card in
    A-07-T23; the old rows stay readable.
- **Freeze language.** The Dec 24, 2027 live-path cut, the Jan 1 – Apr 20, 2028 window and the
  train dates are calendar notes under AMENDMENT-solo; "both founders" is the one builder.

## 3. Live-path files (pre-existing files A-07 edits; merge by Fri Dec 24, 2027)
| File | A-07 change | Task |
|---|---|---|
| `backend/src/abacus/modules/assurance/gates.py` (protected, red) | G6–G9 providers through `register_gate_provider` | T15 |
| `backend/src/abacus/modules/assurance/release.py` (protected, red) | the release transaction and `ReleaseWorkflow` entry | T30 |
| `backend/src/abacus/modules/assurance/archive_gate.py` (protected, red) | archive checklist and G9 live facts | T31 |
| `backend/src/abacus/modules/assurance/phase.py` | derived phases `completion`, `ready_to_release`, `released`, `archiving`, `archived` | T15 |
| `backend/src/abacus/modules/assurance/completion.py`, `completion_routes.py`, `completion_models.py`, `completion_repository.py`, `completion_decisions.py` | record-mode slice: reads move to the projector; routes retired at T33 | T22, T33 |
| `backend/src/abacus/modules/assurance/routes.py`, `registry.py`, `events.py`, `api.py` | router mounts, registrations, outbox events, `record_acknowledgement` | T04, T05, T19, T26 |
| `backend/src/abacus/modules/evidence/workflows.py`, `storage.py` | `ArchiveLockWorkflow`, `SealVerifyWorkflow`; COMPLIANCE writes and `_extend_retention` | T37, T42 |
| `backend/src/abacus/kernel/db/migration.py`, `kernel/uow/__init__.py` | `archived_guard()`, the `tenant_table()` hook, `uow.allow_archived_write(kind)` | T13 |
| `backend/src/abacus/modules/engagements/service.py`, `engagements/api.py` | `engagement.archive` becomes a system transition; `is_archived()` reads the work-item lock | T14 |
| `backend/src/abacus/modules/notifications/catalogue.py` | A-07 §4.8 kinds | T19 |
| `backend/src/abacus_tools/codegen/permission_matrix.py` | `archived_exempt:<kind>` and its generated tests | T14 |
| `backend/src/abacus_tools/quality/banned_patterns.py` | ARCHIVE-001, RELEASE-001 | T13, T30 |
| `docs/architecture/permission-matrix/assurance.yaml`, `evidence.yaml` | A-07 §4.4 rows | T04, T05, T14 |
| `docs/architecture/human-only-actions.yaml` | I-AGENT-NEVER rows for every final verb | T04, T05 |
| `docs/architecture/error-codes.yaml` | A-07 §4.3 codes | T04, T05 |
| `docs/architecture/feature-flags/` | the four `audits.*` flags | T33 |
| `docs/product/status-vocabulary.yaml`, `docs/product/glossary.md` | A-07 words and phases | T03 |
| `backend/mutation-thresholds.yaml` | floors for the red files | T45 |
| `docs/architecture/protected-paths.md`, `.claude/hooks/_protected.py` | no new entry: `evidence/archive.py` and `evidence/seal.py` sit inside the red `evidence` module; T01 confirms the list | T01 |

New files (dark until the flags): `assurance/{eqr,completion_projector,subsequent_events,rep_letter,governance,report,filings,clocks,workflows}.py`, `assurance/completion/_dark.py`, `assurance/completion_contract.py`, `assurance/release_contract.py`, `evidence/archive.py`, `evidence/seal.py`, `kernel/db/archive_guard.py`, and the four migrations M1–M4.

## 4. Acceptance criteria
Status is the kickoff reconcile against main (SPEC-314/TASK-332, A-01-T23, P-04): only the gaps
become work.

| AC | Task | Sprint | Zone | Criterion | On main at kickoff |
|---|---|---|---|---|---|
| AC-1 | T01 | S27 | red | Both founders accept the SPEC on Mon Nov 1, 2027, it cites only chapter-09 IDs, and the live-path list names every pre-existing file A-07 edits. | missing |
| AC-2 | T02 | S27 | green | Every artboard letter is marked live, fixture-only or deferred with its owning epic, and the link-contract test knows every outbound target. | missing |
| AC-3 | T03 | S27 | amber | make generate emits the new StrEnums and status.ts entries, and no A-07 screen string uses a status word missing from the registry. | missing |
| AC-4 | T04 | S27 | red | The generated client exposes every AUD-18 and AUD-19 operation returning 501, each route declares one matrix action, and the I-AGENT-NEVER generated test covers eqr.concur. | missing |
| AC-5 | T05 | S27 | red | Every AUD-21 to AUD-25 operation is in the generated client returning 501, and the contract doc lists report.release, archive.lock and archive_addition.approve as human-only with fresh MFA. | missing |
| AC-6 | T06 | S27 | amber | The suite runs in notanaskhan's CI against the stubs and fails if any artboard field lacks a server source. | missing |
| AC-7 | T07 | S27 | red | Up/down/up passes, a concurrence written by an agent or system actor is refused by the database, and every new table has forced RLS. | partial — 0077 has insert-only human-only `eqr_concurrences` (one per engagement, `completion_records`); the v2 tables are new |
| AC-8 | T08 | S28 | red | A second original release for the same work item and any UPDATE of a version or release row are refused by the database. | partial — 0077 `releases` (one per engagement, human-only); v2 letters, versions and report tables are new |
| AC-9 | T09 | S28 | red | A lock decision or addition approval written by a non-human actor is refused, and documentation_completion_date for an Oct 9, 2026 release reads Dec 8, 2026. | partial — 0077 `archives` (one per engagement, seal fields); clocks, binder index, manifests and additions are new |
| AC-10 | T10 | S28 | red | Tests written in ayushkbhatia's session pass and fail when any insert-only or human-only trigger is removed. | missing |
| AC-11 | T11 | S28 | green | /components/screens/AUD-25?st=c&frame=1&static=1 reproduces the Thu Dec 3, 2026 4:18 PM CST locked state with seal 7c41…a9e2 from typed fixtures. | missing |
| AC-12 | T12 | S28 | amber | make seed-demo loads every template through the import endpoints, the licensed-text detector reports zero hits, and no template wording appears in Python or TypeScript sources. | missing |
| AC-13 | T13 | S29 | red | On a locked work item every write to a guarded table raises archived, an audit_events insert still succeeds, and the GUC can be set only from the four allowlisted service functions. | missing |
| AC-14 | T14 | S29 | red | The generated route-table test lists every mutating route, all answer 409 archived on a locked work item, and only the declared exempt actions pass. | missing |
| AC-15 | T15 | S29 | red | For a firm on external mode ENG-02 and AUD-02 render exactly as before, and for an in_app work item the G6-G9 rows read their live blockers from the providers. | partial — SPEC-314 computes G6–G9 inside `completion.py`; A-01-T23 registers interim G8/G9 for external mode |
| AC-16 | T16 | S29 | amber | Each report template validates against the DocBlock schema with no unknown variable, and the reason-code popover lists exactly the four codes for Northwind. | missing |
| AC-17 | T17 | S29 | green | All six AUD-18 artboards render from fixtures and no Edit, L1-L4 Sign off or Auto mode control exists for Thomas Whitcombe. | missing |
| AC-18 | T18 | S30 | amber | Concur is refused while any item or EQR note is open, refused for Hannah Leclerc with 403 eqr_only, and on success records G6 and notifies Margaret Okonkwo. | partial — SPEC-314 concur (reviewer role, not-involved CHECK, notes block); no checklist, cards, MFA or eligibility re-check |
| AC-19 | T19 | S30 | red | With every A-07 flag off, AUD-02, ENG-02, SIG-01 and HOME-02 responses for the canary tenant are identical before and after the merge. | missing |
| AC-20 | T20 | S30 | red | Tests written in ayushkbhatia's session fail if a scoped table lacks the trigger or if any file outside the allowlist sets app.archived_write. | missing |
| AC-21 | T21 | S31 | red | The suite fails if the EQR can sign L1-L4 or if G6 reads met before a concurrence row exists. | missing |
| AC-22 | T22 | S31 | amber | Northwind on Tue Oct 6, 2026 reads 12 complete, 1 not applicable and 5 open with exactly five blockers, and a rebuild from events yields identical rows. | missing |
| AC-23 | T23 | S31 | amber | Run #4240 fires at 9:00 AM CDT on Oct 9, 2026 in the time-skipping test, re-arms when the report date moves, and never records a going-concern conclusion. | partial — SPEC-314 going-concern decision (completion.decide); not yet a C3 card |
| AC-24 | T24 | S31 | amber | Dana Kowalski's Oct 9 signature records G7, an Oct 8 signature yields Date mismatch with Start re-date, and Send is refused before Margaret Okonkwo approves. | partial — SPEC-314 records the signed letter and its date (G7 date check); no composition, approval or envelope |
| AC-25 | T25 | S31 | green | All seven AUD-19 artboards render from fixtures and the summary reads 12 of 17 with N/A excluded. | missing |
| AC-26 | T26 | S32 | amber | The Northwind planning letter reaches only Benefits Committee grant holders, Dana Kowalski's management grant cannot read it (INV-4), and an acknowledgement moves the row to Acknowledged. | missing |
| AC-27 | T27 | S32 | amber | An agent PATCH of opinion_form is refused at every layer, Qualified without a decided card answers 409 decision_required, and two DOCX renders of v2 are byte-identical. | partial — SPEC-314 report record and partner approval; no builder, templates or renders |
| AC-28 | T28 | S32 | green | All seven AUD-21 artboards render from fixtures, general paragraphs read Always included, and Send for signature… is disabled outside the approved state. | missing |
| AC-29 | T29 | S32 | green | All seven AUD-22 artboards render from fixtures and only Margaret Okonkwo's persona sees Approve & send…. | missing |
| AC-30 | T30 | S33 | red | Margaret Okonkwo's 10:07 AM release records G8 once under replay, a render failure records nothing, and agent, system and stale-MFA calls are refused. | partial — SPEC-314 release re-checks G5–G7 in one unit; no grant, workflow, C11 render, C10 publish or MFA |
| AC-31 | T31 | S33 | red | On Thu Oct 22, 2026 Northwind reads Archive in 47 days, 8 of 9 with one named open item, and a binder index of 26 workpapers and 24 source documents. | missing |
| AC-32 | T32 | S33 | red | Each run appears in the AUD-18, AUD-19 and AUD-25 docks with its ToolCards, cites only verified sources, and the gateway records zero model calls for it. | missing |
| AC-33 | T33 | S33 | red | make check-fast passes, no A-07 flag expires between Jan 1 and Apr 20, 2028, and every A-07 route answers 404 for a firm with its flag off. | missing |
| AC-34 | T34 | S33 | green | All ten AUD-23 artboards render from fixtures and no paragraph text is editable as free text. | missing |
| AC-35 | T35 | S33 | red | The suite fails if any letter reaches a client principal before a named EP approval or if a regenerate drops a human edit. | missing |
| AC-36 | T36 | S34 | amber | Golden clocks hold: an Oct 9 release gives Dec 8 for both clocks, Archive in 5 days on Dec 3, and Overdue on Dec 9. | missing |
| AC-37 | T37 | S34 | red | Locking Northwind on Dec 3, 2026 yields a seal whose recomputation is byte-identical, a records object retained in COMPLIANCE mode to Oct 9, 2031, and evidence retained to Oct 9, 2033. | partial — SPEC-314 Merkle seal over reviewables, documents, concurrence and release; no COMPLIANCE manifest, run records or checkpoint root |
| AC-38 | T38 | S34 | green | All six AUD-24 artboards render from fixtures and Release report… is enabled only in state a for Margaret Okonkwo's persona. | missing |
| AC-39 | T39 | S34 | green | All six AUD-25 artboards render from fixtures and no delete control exists anywhere in states c and d. | missing |
| AC-40 | T40 | S34 | amber | The suite passes at 1.0 on every threshold and fails when a seeded narration claims 'approved' or a digest card cites an undecided card. | missing |
| AC-41 | T41 | S34 | amber | make seed-demo and fixture mode show identical AUD-18 to AUD-25 data and the scenario writes only through service APIs. | missing |
| AC-42 | T42 | S35 | red | The PI-02 memo is appended on Jan 15, 2027 only after Margaret Okonkwo approves, the original seal is unchanged, and a tampered row makes verify report seal_mismatch. | missing |
| AC-43 | T43 | S35 | amber | Every figure above holds on make seed-demo and the tests fail on a one-day or one-row drift. | missing |
| AC-44 | T44 | S35 | green | Tests written in notanaskhan's session fail if any final verb renders as done before the server confirms it. | missing |
| AC-45 | T45 | S35 | red | backend/mutation-thresholds.yaml records the floors and the p95 budgets hold on staging. | missing |
| AC-46 | T46 | S35 | red | The vendor report is in hand by Fri Mar 3, 2028 and every critical and high is fixed and retested before Tue Mar 21, 2028. | missing |
| AC-47 | T47 | S35 | green | On staging Hannah Leclerc's AUD-19 updates within 10 s of Dana Kowalski signing, and every A-07 screen runs with VITE_FIXTURES unset. | missing |
| AC-48 | T48 | S35 | green | All locked artboards pass Tier C with the DF-11 and DF-20 copy deviations masked and recorded, and axe reports zero violations. | missing |
| AC-49 | T49 | S36 | red | Tests written in ayushkbhatia's session fail if a release can be recorded with any gate unmet or if a locked row changes. | missing |
| AC-50 | T50 | S36 | green | j03 steps 15-19 and j18 steps 5-6 pass on staging with every invariant asserted and axe clean. | missing |
| AC-51 | T51 | S36 | red | The runbook is rehearsed on staging and the flip request carries passing journeys, shadow evidence, the delta-test closure and both approvals. | missing |
| AC-52 | T52 | S36 | red | validate_docs is green and a fresh session can add a guarded table and an exception kind from the docs alone. | missing |
| AC-53 | T53 | S36 | green | Every A-07 artboard in the manifest shows its final status and the guide renders from the database in the in-app help. | missing |

## 5. Task map (S27)
T01 (this SPEC) → T03 (words) → T04 and T05 (contract stubs) → T07 (migration M1) → T02 (screen
contracts) → T06 (consumer contract tests). T08–T53 follow the epic's sprint order (S28–S36).

## 6. Out of scope
A-07 §2.3, unchanged: AUD-15/16/17/20 (A-06), AUD-26 (A-08), AUD-28/30, ADM-12, FIL-02 (Q-05),
POR-09/15 (R-02), FSP-06 (A-10), XLA-02 (W-04), model-drafted client text (P-25 stays off),
EFAST2 integration, PCAOB forms (X-07), single audit (D10).
