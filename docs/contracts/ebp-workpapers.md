# ebp-workpapers v1 — the A-05 EBP plan audit contract

| Field | Value |
|---|---|
| Owner | assurance (A-05; SPEC-640) |
| Status | stub (A-05-T04, 2026-11-01); live per route with its A-05 task |
| Code | `backend/src/abacus/modules/assurance/ebp_contract.py` |
| Tests | `backend/tests/contracts/a05_ebp/test_a05_stub.py` |
| Screens | EBP-01 to EBP-09, AUD-27 (`docs/screens/`) |

## Callers
The firm SPA's EBP screens and AUD-27 (A-05 §5), A-04's section drafter in its EBP modes (reads at
task scope), A-06's AUD-20 (the Form 5500 reconciliation note) and A-03's sampling (the tests grid
reads sample sets). No portal or API scope reads any route here (INV-4).

## Routes
All under `/v1/audits/{work_item_id}`, one matrix action each, behind a flag: `ebp.modules` (EBP-01
to 06, 08, 09 and the tests grid), `ebp.form5500_tieout` (EBP-07), `assurance.estimates_rp`
(AUD-27). The gate answers a client principal 404, authorises the action on the work item's
engagement (walls 404, independence 403) and then reads the flag (404 off). A read answers the
Northwind Robotics 401(k) Plan PY2025 seed's figures; a write is 501 `not_implemented` until its
task. Writes take `Idempotency-Key`.

| Method and path | Shape | Action | Live with |
|---|---|---|---|
| GET `/ebp/plan` · PATCH `/ebp/plan` | `PlanOut` · `PlanEditIn` | `ebp.read` · `ebp_plan.edit` | T08 |
| GET/POST `/ebp/providers` · POST `/ebp/providers/{id}/invite` | `ProvidersOut` · `ProviderIn` · `InviteIn` | `ebp.read` · `ebp_provider.manage` · `ebp_provider.invite` | T08 |
| GET `/ebp/plan-reviews/current?version=` · POST `/ebp/plan-reviews` | `PlanReviewOut` (verified = a current field tick on the value cell) · `PlanReviewIn` → `AcceptedOut` (the run id; `workpapers.drafting` too) | `ebp.read` · `workpaper.draft` | T10, T12; served T16. EBP-02's L1/L2 sign-off answers 409 `sign_off_blocked` with `facts.reason` `provisions_unverified` and `facts.count` until every provision is verified (DEC-2069) |
| GET `/ebp/participants` · POST `/ebp/participants/{id}/reveals` · POST `/ebp/imports` · GET `/ebp/imports/{id}` | `ParticipantsOut` · `RevealIn` → `ParticipantRevealOut` (`no-store`) · `ImportIn` → `ImportOut` (422 `import_refused`, recorded, with `facts.reason`, `column`, `difference`) | `ebp.read` · `pii.reveal` · `ebp_import.create` · `ebp.read` | T15; served T18 (reveal), T19 (imports, participants) |
| POST `/tests` · PUT `/tests/{tid}/items/{iid}/results/{attr}` | `TestIn` · `ResultIn` | `test.create` · `test.mark` | T17 |
| GET `/ebp/eligibility` | `FiguresOut` | `ebp.read` | T19 |
| GET `/ebp/contributions/test` | `TestGridOut` (cells add `value`, `expected`; rows add `linked_item_id`) | `ebp.read` | A-05-T32 stub, 501 (DEC-2258) |
| GET `/ebp/contributions/payrolls` | `list[PayrollOut]` (pay date, deposit, lags, total by code, late) | `ebp.read` | A-05-T31 (DEC-2257) |
| GET `/ebp/contributions/reconciliation` · GET `/ebp/late-remittances` · POST `/ebp/late-remittances/{id}/corrections` | `FiguresOut` · `LateRemittanceOut` · `CorrectionIn` | `ebp.read` · `ebp_correction.record` | T20, T21 |
| GET `/ebp/loans/rollforward` | `FiguresOut` | `ebp.read` | T31 |
| GET `/ebp/investments?layer=` · POST `/ebp/trust-tb/adopt` · PUT `/ebp/certification/points/{key}` | `FiguresOut` · `TrustAdoptIn` · `CertificationPointIn` | `ebp.read` · `ledger_snapshot.create_from_document` · `ebp_certification.evaluate` | T26, T27, T28 |
| GET `/ebp/participant-accounts/rollforward` | `FiguresOut` | `ebp.read` | T46 |
| GET `/ebp/plan-expenses` | `FiguresOut` | `ebp.read` | T44 |
| GET `/ebp/form-5500` · POST `/ebp/form-5500/lines/{id}/value` · POST `/ebp/form-5500/reconciliation-note` | `Form5500Out` · `LineValueIn` | `ebp_form5500.read` · `ebp_form5500.key` · `ebp_form5500.send_note` | T36, T38 |
| GET/PUT/POST `/estimates*` · `/related-parties*` · `/parties-in-interest` | `Aud27ListOut` · `MethodIn` · `Aud27ItemIn` · `ScreenOutIn` | `estimate.*` · `related_party.*` · `party_in_interest.manage` | T50, T52 |

**Form 5500 read (A-05-T58; DEC-2814), additive.** `Form5500Out` gains `rows` (one
`Form5500RowOut` per Schedule H line: `line_code`, `caption`, `fs_amount`, `f5500_amount`,
`difference`, `classification` tie / reconciling_item / inconsistent, `note_ref`, `match_id`),
`draft_id` and `evidence_version_id` (the draft's PDF, which the cockpit opens in its viewer dock).
`lines` stays for v1 readers. `match_id` is the cited region's own C4 §3.1 id, read from the line's
`f5500_citation_id` through `citation_display`; a citation the reader can't see, or one with no
region, lights nothing (INV-2: the screen never composes one). With no current draft the read
answers `draft_received = false` and empty lists (EBP-07 d). `part_iv` lists the five lines the
code checks (4a, 4b, 4d, 4i, 4j); `basis` is `evidence_ref.basis` on the stored answer.

**A-05-T58 close (DEC-2820), additive.**
- `part_iv` lists every line 4a to 4m. `consistency` gains `not_checked` for a line no code check covers; code checks 4a.
- `GET /ebp/form-5500/schedules/4i` (`ebp_form5500.read`) answers `Schedule4iOut`. It is the schedule built by code from the trust report's current lines, the participant loans and the plan's parties in interest. Each row has its `*` mark, a cost omitted (`**`) for participant-directed holdings, and the current value. The read also returns the total, the draft's line 1c total and `ties`.
- `POST /ebp/form-5500/lines/{id}/value` is live. A person keys the draft's value with a citation note (sealed, migration 0742), the event audits `ebp_form5500_line.keyed`, and code re-runs the tie-out. The response's `id` is the draft's.

**The Schedule H mapping as content (A-05-T62 close; DEC-2823).** `POST /v1/ebp/schedule-h-mappings:publish` (`ebp_schedule_h_mapping.publish`; quality partner or practice leader; fresh MFA) takes `MappingPublishIn` (`effective_plan_year` and `rows` of `fs_caption_key` with `schedule_h_line`). It defaults to a dry run, which reports `problems` as codes with row places. A clean, non-dry run inserts the next firm-wide version, published, into `ebp_schedule_h_mappings`. No version ever changes.

A-05 §4.3's other routes (provider drawers, population queries, payroll drawer, Schedule H 4a,
loan details, SDBA and vesting, compliance and qualification, render and remind) join additively
with their tasks.

## Status words
`ebp_provider_check` received · waiting_on_inputs · correction_requested; `ebp_late_remittance`
found · pending_vfcp_scc · corrected; Form 5330 exposure · not_required · filed; certification
point not_evaluated · evaluated; Form 5500 line tie · reconciling_item · inconsistent; Part IV
consistent · inconsistent; AUD-27 unevaluated · evaluated · exception · screened_out ("Evaluated ·
pending EP" is a display variant). The registry rows land with A-05-T05.

## Human-only actions (INV-1)
Every one denies the agent and the system at the matrix:
- **verify** a provision (`field.sign_off` on an `ebp_provision`, L1);
- **adopt** the trust report as the plan TB (`ledger_snapshot.create_from_document`) and a test
  result (`test.mark`);
- **record correction** of the late remittance (`ebp_correction.record`; time alone never
  corrects);
- **evaluate certification** points (`ebp_certification.evaluate`, 29 CFR 2520.103-8);
- **conclude** an estimate or a finding (`decision.decide` on the EP's card, raised by
  `estimate.request_conclusion`).

## Classification
A participant's SSN and date of birth are Restricted and leave the server only as masks
(`ssn_masked` `•••-••-NNNN`, `dob_masked`; DEC-1858); a reveal is `pii.reveal` (fresh MFA,
onshore, logged). Compensation, balances and every figure are Confidential.

## Audit events
Every write records its act through the unit of work once live: `ebp_plan.edited`,
`ebp_provider.added`, `ebp_provider.invited`, `ebp_import.created`, `pii.revealed` (never the
value), `test_result.marked`, `ebp_late_remittance.corrected`, `ebp_certification_point.evaluated`,
`ledger_snapshot.created_from_document`, `ebp_form5500_line.keyed`, `estimate.evaluated`,
`related_party.added`, `related_party.screened_out`, `related_party.activity_recorded` (S31 close).
