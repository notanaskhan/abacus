# Team, acceptance, independence and conflicts · ENG-05, CLI-07, CLI-08, CLI-06 (v1)

| Field | Value |
|---|---|
| Register row | Screen-family contracts in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub (P-07-T29, 2026-10-25); ENG-05's team rows and the confirmation requests live (P-07-T30, 2026-10-25; DEC-327); CLI-07's acceptance live (P-07-T35, 2026-10-26; DEC-372); conflicts and screening live (P-07-T36, 2026-10-26; DEC-373) |
| Provider epic | P-07 (`engagements` for team, acceptance and independence; `organisations` for conflicts and screening) |
| Consumers | ENG-05 (P-07-T39), CLI-07 (P-07-T35's screen), CLI-08 (P-07-T48), CLI-06 (conflicts); the consumer suite P-07-T31; HOME-02 gate rows (T47); P-04 sign-off through `independence_cleared` |
| Freeze sprint | the sprint review after the stub (P-07 §8.1) |
| Flags | `engagements.acceptance_v2` for acceptance, independence, conflicts and screening (default off, created 2026-10-25, expires 2027-04-21 under DEC-137's override); `engagements.v2` for ENG-05's team rows (the screen's flag) |
| Spec | `docs/specs/SPEC-332-acceptance-independence-conflicts-in-app.md`; P-07 §3.4, §3.5, §4.2 M4 to M7 |
| ADRs | ADR-005, ADR-026, ADR-031, ADR-139 (P-36), ADR-147, ADR-164; DEC-39, DEC-43, DEC-63, DEC-64, DEC-91, DEC-326, DEC-327 |

## 1. Purpose
Consumers can rely on: ENG-05's team roster extras (budget hours, the portal flag, the EP's team approval and its "changes since" facts, the EQR candidate list with eligibility per check, EQR assignment and the quality owner's eligibility approval); CLI-07's acceptance record (questionnaire sections from the firm's pinned template version, flags with sources, manual checks, send to partner, risk-partner review, the three-option decision with conditions); CLI-08's independence summary (confirmations, banner reasons, conclusion), rotation, NAS rows, breaches, reminders and the EP's conclusion; CLI-06's conflict checks with redacted walled matches, clearance and human-recorded screening.

**Behaviour.** Every route first refuses a client principal, an agent and the system and authorises its action (a walled or unknown engagement 404), and only then reads its flag (DEC-326). With `engagements.acceptance_v2` off, every acceptance, independence (except the reminders), conflict and screening route answers 404; with it on, the acceptance (P-07-T35), conflict and screening (P-07-T36) routes are live, and independence v2 answers 501 `not_implemented` until P-07-T41. An engagement with no acceptance record answers 404 on the acceptance routes; a record is opened by ENG-03's "Start acceptance" (`engagements-v2.md`) or, later, the intake commit (P-07-T42).

**Acceptance as built (P-07-T35, DEC-372).** The record is pinned to the newest version of the firm's questionnaire template for the engagement type's family (database content; none: 409 `acceptance_template_missing` on start). A section's `version` is 0 until its first answer, and `seen_version` on an answer is the section's. A manual check is asked of someone who holds the prepare right on this engagement (engagement partner, manager, client service; 422 `invalid` otherwise, or while the section has an open check) and only that person completes it (403). Client service may do nothing else here. Send to partner needs `seen_version` (the record's) and no open check. The decision needs an Awaiting-partner record (409 `acceptance_not_ready` in Draft), the record's `seen_version`, a rationale for every option (SPEC-332 AC-7 and the CLI-07 deviation), conditions only with Accept with conditions (422 `invalid` otherwise; each assignee an active firm member), and on a High-risk record a completed risk-partner review. The risk partner is a partner-level member who is neither the caller nor an engagement partner here nor walled from the client (422 `invalid`), and only they complete the review. A decided or declined record is locked at the database. SPEC-025's `PUT …/acceptance` stays as an adapter: on an engagement with a record it refuses any decision other than the record's (409 `decision_locked`).

**Conflicts as built (P-07-T36, DEC-373).** A check searches, per name and as a system principal over metadata (2-second statement timeout): clients and client entities by normalised name (`exact`, or `trigram` at a `pg_trgm` similarity of at least 0.6), contacts the same unless the contact holds a counterparty role (custodian, recordkeeper, TPA, payroll provider), which is `counterparty` on its client, and each matched entity's current relationship edges to another client's entity (`relationship`). One result per matched client and kind, the best score. A counterparty result starts as `counterparty_review`, any other as `pending`; the newest clearance event is the assessment, and the check's `outcome` is `hits` while any result is `pending`, `counterparty_review` or `conflict`. Results are redacted per reader at read time; a client or client-entity subject the caller cannot see answers 404 on run and read; draft subjects are references organisations does not read. Names are never stored on results (read at display time); the searched names, reasons and notes are sealed. With `engagements.v2` off, ENG-05's team rows and the reminders answer 404; with it on they are live (P-07-T30; DEC-327 has the eligibility rules).

## 2. Who may call it
Matrix: `docs/architecture/permission-matrix/engagements.yaml` and `organisations.yaml`. Every route is one action.

| Operation | Method and path (under `/v1/engagements/{engagement_id}` unless absolute) | Matrix action | Roles allowed | Agent or system |
|---|---|---|---|---|
| Acceptance record | `GET /acceptance` | `acceptance.read` (new) | engagement partner, manager, senior, staff, reviewer, EQR reviewer, client service; quality partner `in_scope` | denied |
| Answers, flags, manual checks, send to partner, complete a condition | `PUT /acceptance/answers/{section_code}` · `POST /acceptance/flags` · `POST /acceptance/manual-checks/{section_code}/request` and `/complete` · `POST /acceptance/send-to-partner` · `POST /acceptance/conditions/{condition_id}/complete` | `acceptance.prepare` (new) | engagement partner, manager; client service (the service limits them to a manual check assigned to them) | **denied** |
| Risk-partner review | `POST /acceptance/risk-partner-review` | `acceptance.request_review` (new) | engagement partner | **denied** |
| Complete the risk-partner review | `POST /acceptance/risk-partner-review/complete` `{}` | `acceptance.complete_review` (new, P-07-T35) | the derived `firm_partner`, authorised on the client (walls apply); the service admits only the partner the EP named | **denied** (human-only) |
| Decision | `POST /acceptance/decision` | `acceptance.decide` (new) | engagement partner, `mfa_recent` | **denied** (human-only) |
| Independence summary, rotation, NAS rows | `GET /independence` · `GET /independence/rotation` · `GET /independence/nas` | `independence.read` (new) | engagement team (partner, manager, senior, staff, reviewer, EQR reviewer, specialist); quality partner `in_scope` | denied |
| Confirm, decline | `POST /independence/confirm` · `/decline` | `independence.confirm` | team members, for themselves only (409 `not_self`) | **denied** (human-only) |
| Reminders (live with ENG-05, behind `engagements.v2`) | `POST /independence/reminders` | `independence.remind` (new) | engagement partner, manager | **denied** |
| NAS evaluation | `PUT /independence/nas/{service_code}` | `nas.evaluate` (new) | engagement partner, manager (the decision the EP's) | **denied** |
| Breaches | `POST /independence/breaches` · `POST /independence/breaches/{breach_id}/events` | `independence.breach_manage` (new) | engagement partner, manager, quality partner | **denied** |
| Conclusion | `POST /independence/conclude` | `independence.conclude` (new) | engagement partner, `mfa_recent` | **denied** (human-only) |
| Team approval footer | `GET /team/approval` | `engagement.read_metadata` | as the team read | as that row |
| Approve the team | `POST /team/approve` `{member_set_hash}` | `team.approve` (new) | engagement partner, `mfa_recent` | **denied** (human-only) |
| Portal visibility | `PUT /team/{user_id}/portal-visibility` | `engagement.update` | engagement partner, manager | denied |
| EQR candidates, assign | `GET /eqr/candidates` · `POST /eqr` | `eqr.assign` (new) | engagement partner, manager | **denied** |
| EQR eligibility approval | `POST /eqr/eligibility/approve` | `eqr.approve_eligibility` (new) | quality partner, never the EP (409 `eqr_approver_is_ep`) | **denied** (human-only) |
| Run and read a conflict check | `POST /v1/conflict-checks` · `GET /v1/conflict-checks/{check_id}` | `conflict.run` (new) | firm admin, partner (`firm_partner`), manager (`firm_manager`) | denied |
| Clear a result | `POST /v1/conflict-checks/{check_id}/results/{result_id}/clear` | `conflict.clear` (new) | partner (`firm_partner`), manager (`firm_manager`) | **denied** (human-only) |
| Record a screening result | `POST /v1/screening-records` | `screening.record` (new) | firm admin, partner (`firm_partner`), manager (`firm_manager`) | denied |

No client role holds any action here. A walled engagement or client answers 404 on every route (INV-3). The plan's manager cells on `conflict.run`, `conflict.clear`, `screening.record` and `client.intake` are the derived `firm_manager` (a manager-level staff member at firm level, as `firm_partner` is for partners; P-07-T36, DEC-373).

## 3. Models
Code: `backend/src/abacus/modules/engagements/acceptance_contract.py` and `backend/src/abacus/modules/organisations/conflicts_contract.py`. Every field carries a classification tag; free text is confidential and sealed at rest.

- **Acceptance:** `AcceptanceRecordOut` (`kind` new_client · new_engagement_existing_client · continuance; `status` C2 `acceptance_record`; `template_version_id` and `template_name` from the firm's database template; `risk_rating` low · moderate · high; `sections` `AcceptanceSectionOut` with `answer_state` pending · complete · flag · manual_check_open · manual_check_done and `manual_check`; `flags` `AcceptanceFlagOut` with `severity` low · medium · high and `sources` (`kind` evidence_version · request_item); `decision` `AcceptanceDecisionOut` with `option` accept · accept_with_conditions · decline; `conditions`; `risk_partner_review`; `prior` for a continuance; `version`; `allowed_actions`). Inputs: `AcceptanceAnswersIn` (`seen_version`, `answers`, `complete`, `risk_rating`), `AcceptanceFlagIn`, `ManualCheckRequestIn`, `ManualCheckCompleteIn`, `SendToPartnerIn`, `ConditionCompleteIn`, `RiskPartnerReviewIn`, `RiskPartnerReviewCompleteIn` (empty), `AcceptanceDecisionIn` (`option`, `rationale`, `conditions` with assignee and optional due date, `seen_version`).
- **Independence:** `IndependenceSummaryOut` (`attest_client`, `confirmed` of `total`, `members` `MemberConfirmationOut` with `confirmation` requested · confirmed · declined, `blockers` `IndependenceBlockerOut` reason codes, `conclusion` `IndependenceConclusionOut` with `option` C2 `independence_conclusion` and `supersedes_id`, `ske_designee_contact_id`), `RotationOut` (`review_years`, rows with `years_served` and `familiarity_flag`), `ConfirmIn` (`statement_version`, `statement_codes`, `interests_note`), `DeclineIn` (`note`), `ConfirmationOut`, `RemindersIn` / `RemindersOut`, `NasOut` / `NasRowOut` (`status` C2 `nas_evaluation`) / `NasEvaluationIn`, `BreachIn`, `BreachEventIn` (`kind` evaluated · tcwg_communicated · remediated), `BreachOut` (`resolved`), `ConcludeIn` (`option`, `safeguards`).
- **Team and roles:** `TeamApproveIn` (`member_set_hash`), `TeamApprovalOut` (`member_set_hash` of the current team, `approved_by`, `approved_by_name`, `approved_at`, `changed`, `added_since`), `PortalVisibilityIn` / `Out`, `EqrCandidateOut` (`eligibility` eligible · not_eligible, `checks` `EqrCheckOut` with `code` not_on_team · cooling_off · competence · independence · capacity, `result` pass · fail · pending · not_assessed, `count` for competence, `year` for cooling-off, `current`), `EqrIn` / `EqrOut`, `EqrEligibilityApprovalIn` / `Out`. The live team routes (`GET/POST/PUT/DELETE /team`) take `specialist` and `budget_hours` (PUT: role and hours, either or both) and return `TeamRosterMemberOut` (`TeamMemberOut` + `budget_hours`, `shown_on_portal`, `proposed_at`, `independence` requested · confirmed · declined); C1's engagement projection keeps `TeamMemberOut` (P-07-T30, DEC-327).
- **Conflicts:** `ConflictCheckIn` (`subject` kind and id, `names` 1–50), `ConflictCheckOut` (`outcome` pending · clear · hits, `results`), `ConflictResultOut` (`redacted`, `match_kind` exact · trigram · relationship · counterparty, `assessment` C2 `conflict_assessment`; when `redacted` is true, `matched_client_id`, `matched_name`, `matched_ref_*` and `score` are null), `ConflictClearIn` (`assessment` clear · same_family_not_adverse · not_adverse · counterparty_review · conflict, `reason`), `ScreeningRecordIn` / `Out` (`screening_list` ofac_sdn · adverse_media · restricted_entities, `result` no_match · match · not_applicable, `evidence_version_id`).

No model has a hidden-by-wall field or a count of walled matches (DEC-43, DEC-64).

## 4. Status words
C2: `acceptance_record`, `nas_evaluation`, `independence_conclusion`, `conflict_assessment`. The clearance code `conflict` (AC-25) joined `conflict_assessment` with P-07-T36 ("Conflict", red-tint, terminal). Confirmation states (requested, confirmed, declined), answer states and EQR results are fields not named `status`, so they are not registry statuses.

## 5. Human-only actions
`acceptance.decide`, `acceptance.complete_review`, `independence.confirm`, `independence.conclude`, `conflict.clear`, `team.approve` and `eqr.approve_eligibility` deny `agent` and `system` at the matrix (the generated matrix and resolution tests hold it from the stub onward), at `require_live_human` in the live services, and at an `actor_kind = 'human'` CHECK on the rows they write. Their audit actions (`acceptance.decided`, `independence.confirmed`, `independence.concluded`, `conflict.cleared`, `team.approved`, `eqr.eligibility_approved`) join `docs/architecture/human-only-actions.yaml` with the migration that first writes them (`team.approved` and `eqr.eligibility_approved` with 0155; `acceptance.decided` and `acceptance.review_completed` with 0163; `conflict.cleared` with 0164). Only `engagements/acceptance.py`, its route and `engagements/api.py` name `decide_acceptance` (banned pattern ACCEPT-001); only `organisations/conflicts.py`, its route and `organisations/api.py` name `clear_conflict_result` (CONFLICT-001).

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not found"}` | the flag off; a walled or unknown engagement, client, check or result; a result on a client the caller is walled from (clearing it) |
| 501 | `{"detail": "not_implemented"}` | the flag on, before the implementing task |
| 409 | `decision_locked` | any edit after the acceptance decision |
| 422 | `rationale_required` (`facts.field` `rationale` or `conditions`) | an empty rationale; Accept with conditions without a condition |
| 409 | `acceptance_not_ready` (`facts.section`, `facts.open_checks`) | send to partner with a manual check open; a decision on a record still in Draft |
| 409 | `acceptance_template_missing` (`facts.family`) | start acceptance when the firm has no questionnaire for the type's family |
| 409 | `illegal_transition` | send to partner a second time |
| 422 | `invalid` (`facts.field`: `requested_of`, `section_code`, `partner_id`, `conditions`; or `facts.condition_id`) | a manual check asked of someone who may not complete it, or a second open check; a risk partner who is the EP, an engagement partner here, not a partner or walled; conditions on Accept or Decline; a condition completed twice |
| 409 | `review_required` | a High-risk decision before the risk-partner review is complete |
| 409 | `letter_before_acceptance` | a letter dated before the G1 decision (exists) |
| 409 | `independence_preconditions_unmet` (blockers as facts) | a conclusion with a member unconfirmed, a conflict not cleared, or (attest) no SKE designee or a NAS row undecided |
| 409 | `not_self` | confirming or declining for someone else |
| 409 | `eqr_on_team` | an EQR who holds a team role, or a team role for the EQR |
| 409 | `eqr_not_eligible` (`facts.checks`) | assigning a candidate who fails a check |
| 409 | `eqr_approver_is_ep` | the EP approving the EQR's eligibility |
| 409 | `eqr_approver_on_engagement` | anyone else with a role on the engagement approving it (manager, team member, specialist, the EQR) |
| 409 | `eqr_approval_required` | assigning a candidate whose competence is not assessed before the quality owner approved them |
| 409 | `stale_version` (`facts.engagement_id`) | approving a team that changed since `member_set_hash` was read |
| 403 | `{"detail": "forbidden"}` | a client principal, an agent or the system on any route here, before the flag is read; a client principal on the team reads |
| 422 | `invalid` (`facts.user_id` or `facts.field`) | a reminder to a member whose confirmation is not open; the candidate approving themself |
| 409 | `stale_version` · `gate_unmet` | as elsewhere |

## 7. Audit and outbox events
Audit (one per state change, same unit of work): `acceptance.record_opened` and `engagement_draft.started_acceptance` (start acceptance, with `engagement.created`), `acceptance.answers_updated`, `acceptance.flag_added`, `acceptance.manual_check_requested/completed`, `acceptance.sent_to_partner`, `acceptance.review_requested/completed`, `acceptance.decided`, `acceptance.condition_completed`, `independence.confirmed/declined/reminded/concluded`, `nas.evaluated`, `independence_breach.logged/updated`, `team.approved`, `team.portal_visibility_changed`, `eqr.assigned`, `eqr.eligibility_approved`, `conflict_check.run`, `conflict.cleared`, `screening.recorded`. Outbox (identifiers and codes only): `acceptance.sent_to_partner`, `acceptance.decided`, `independence.confirmed`, `independence.concluded`, `gate.met`, `team.approved`; a reminder re-emits `independence.requested`.

## 8. Example payloads
Brightwater Hale, synthetic; ids are placeholders.

`GET …/eqr/candidates` (ENG-05 c, Fairhaven): `[{"display_name": "Thomas Whitcombe", "eligibility": "not_eligible", "checks": [{"code": "cooling_off", "result": "fail", "year": 2024}, …]}, {"display_name": "Celia Marsh", "eligibility": "eligible", …}]`.

`POST /v1/conflict-checks` → 201 with a walled match as `{"id": "…", "redacted": true, "match_kind": "trigram", "assessment": "pending", "matched_client_id": null, "matched_name": null, …}`.

## 9. Consumer contract tests
- Stub: `backend/tests/contracts/acceptance_independence/test_acceptance_independence_stub.py`.
- Consumers (P-07-T31): the decision and conclusion option sets and the redacted conflict-row shape.

## 10. Versioning
| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | | | stub 2026-10-25 (P-07-T29); ENG-05 live 2026-10-25 (P-07-T30); acceptance live 2026-10-26 (P-07-T35, additive: the completion route); conflicts and screening live 2026-10-26 (P-07-T36) |

## 11. Open points
- DEC-326: the NAS read is `independence.read` (the table names `nas.evaluate` for GET and PUT); `acceptance.prepare` includes client service for manual-check completion; the risk rating is set with a section's answers; `GET /team/approval` is new (the footer needs its own read beside the roster list); `eqr_not_eligible` is a new code.
- DEC-372: the acceptance record as built (P-07-T35): G1's source, the review completion route, the rationale rule, the adapter, the deferred legacy conversion.
- DEC-373: conflicts and screening as built (P-07-T36): the derived `firm_manager`, the search rules, redaction at read time, the outcome.
