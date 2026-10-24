---
id: SPEC-332
title: "Acceptance, independence and conflicts performed in-app (P-07): the questionnaire, the three-option decision, G1 date order, G2 v2, the independence conclusion, NAS, redacted conflict matches, rotation and breaches"
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-005, ADR-026, ADR-031, ADR-136, ADR-147, ADR-160, ADR-164]
related_specs: [SPEC-025, SPEC-321]
created: 2026-10-24
updated: 2026-10-24
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

> **Supersedes SPEC-025's non-goal** "Performing acceptance, independence or conflicts procedures
> inside Abacus (recorded only)" and, in part, SPEC-025 AC-4, AC-5 and AC-7 (TASK-044, TASK-045):
> DEC-64 (b) brings acceptance, independence and conflicts into the product, staged (a human-only
> questionnaire first; any AI pre-screen later, behind the data boundary), and DEC-39 (b) with
> ADR-164 (P-13) re-scopes the independence gate. SPEC-025's other ACs stand. Written for P-07-T02
> (TASK-1120); the epic is `docs/plan/epics/P-07.md` §3.3 to §3.5 and §4. Every AC below carries
> the number the ADR-078 suites (P-07-T26, T38, T43, T44) cite.

## 1. Summary
A firm decides acceptance and continuance (G1) in-app on a questionnaire from its own database
template, with a partner-only three-option decision and conditions; each team member confirms
their own independence and the engagement partner concludes (G2), with NAS evaluation and an SKE
designee for attest clients; conflict checks run in-app with matches on walled clients redacted;
rotation and breaches are tracked. Independence gates assignment, sign-off and client-facing
actions on attest clients only, not content reads (G2 v2).

## 2. Problem and context
SPEC-025 recorded the outcome of procedures done elsewhere ("record, don't rebuild"): one
insert-only `engagement_acceptance` row and per-member confirmations that gate every content read
on every engagement (TASK-045). The designed screens (CLI-06 conflicts, CLI-07 acceptance, CLI-08
independence, ENG-05 team) perform the procedures, and DEC-39 chose a narrower gate: a pending
member can view but cannot be assigned, sign off or act client-facing, and only for attest clients
(ADR-164). This spec is the contract for those behaviours.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Manager, partner (preparer) | Prepares the acceptance record: answers, flags, manual checks, send to partner; runs conflict checks; records screening; prepares NAS rows |
| Client service | Completes a manual check assigned to them |
| Engagement partner | Decides acceptance (fresh MFA); concludes independence (fresh MFA); decides each NAS evaluation; picks the risk partner |
| Risk partner | Another partner the EP names; reviews a High-risk record before the decision |
| Each team member | Confirms or declines their own independence |
| Quality partner (in scope) | Reads records; manages breaches |
| Agent, system | Denied every decision and confirmation; conflict search runs as a system principal over metadata only |

## 4. Goals and non-goals
**Goals:** the questionnaire, three-option decision and conditions (CLI-07); G1 date order;
G2 v2 in `authorise`; confirmation, decline and conclusion (CLI-08); NAS and the SKE designee for
attest clients; redacted conflict results and human-recorded screening (CLI-06); rotation and
breaches (CLI-08 d, g).

**Non-goals:** the AI pre-screen (CLI-07 a/c/d's run card is fixture-only until the data boundary
allows it; DEC-64); automated OFAC or adverse-media lookups (screening is recorded by a person);
the annual firm-wide confirmation (DEC-91, collected in ADM-02 by G-01, DF-07; it joins the
cleared predicate then); e-signature (N-02 replaces the interim G3 provider); SEC/PCAOB rules.

## 5. User stories and acceptance criteria
### Story 1: the acceptance questionnaire (CLI-07 b, f)
- **AC-1** Given an acceptance record in Draft, then its sections come from the firm's database questionnaire template at a pinned immutable version (never a constant), each section has a state (`pending`, `complete`, `flag`, `manual_check_open`, `manual_check_done`), and "Send to partner" is refused (409 `acceptance_not_ready`, the open sections as identifier facts) until every manual check is complete.
- **AC-2** Given a preparer adds a flag (title, severity Low · Medium · High, body, source links to files or requests as object references), then the flag row is insert-only, records the person as author with `authored_kind = 'human'` (CHECK), and its sources open the viewer (SHL-08); no flag cites model output.
- **AC-3** Given "Send to partner", then the record moves Draft → Awaiting partner, `acceptance.sent_to_partner` is audited and emitted, and the engagement partner gets the `acceptance_awaiting_partner` notification.
- **AC-4** Given risk rating High, then "Decide" is refused with 409 `review_required` until a risk-partner review by another partner (picked by the EP, never the EP) is recorded as complete.
- **AC-5** Given a continuance record (kind `continuance`), then it shows the prior-year decision, conditions and independence outcome through the `prior_engagement_id` chain, read-only.

### Story 2: the three-option decision and conditions (CLI-07 a, d, e)
- **AC-6** Given the engagement partner with fresh MFA and a non-empty rationale, when they pick Accept, Accept with conditions or Decline, then exactly one insert-only decision row is written (`record_id` UNIQUE, `actor_kind = 'human'` CHECK), `acceptance.decided` is audited in the same unit of work, and the record locks; a later edit to answers, flags or the decision answers 409 `decision_locked`.
- **AC-7** Given an empty rationale, then 422 `rationale_required`; given Accept with conditions and no condition, then 422 `rationale_required` with `{"field": "conditions"}`.
- **AC-8** Given Accept or Accept with conditions, then the engagement moves Prospect → Accepted through the F-03 transition table and G1 is met with `decided_at`; given Decline, then reasons are required, the engagement moves to Declined and no letter can be recorded (409 `gate_unmet` G1).
- **AC-9** Given a condition, then it carries an assignee and an optional due date, its completion is an insert-only event by a person, and open conditions stay listed on the record and on HOME-02 once C13 is registered.
- **AC-10** Given anyone other than the engagement partner, a system run or the agent principal, then `acceptance.decide` is denied at the matrix, `require_live_human`, the database CHECK and the banned-pattern rule naming the only module allowed to call the decision function (INV-1).

### Story 3: G1 date order (CLI-07, ENG-02, ENG-03)
- **AC-11** Given a recorded letter, then its signature dates must be on or after the G1 `decided_at`, else 409 `letter_before_acceptance`; G1 < letter < first sign-off (R-06), and the first sign-off is refused before G3.
- **AC-12** Given ENG-03 without an acceptance decision for the client, service and period, then step 1's Next is refused and a create answers 409 `gate_unmet` with `{"gate": "G1"}`; "Start acceptance" creates a Prospect engagement and an acceptance record from the draft.

### Story 4: G2 v2, view versus assign (ENG-05, CLI-08; ADR-164 items 2 to 4)
- **AC-13** Given an attest client's engagement and a team member who has not confirmed independence for it, then that member reads the engagement and its content (200), but `work_item.assign` naming them answers 409 `gate_unmet` with `{"gate": "G2", "user_id": …}`, sign-off answers 409 `independence_pending` through `engagements.api.independence_cleared`, and the client-facing actions `message.send`, `request_item.send` and `client_access.grant` are refused for them as the acting member; every other non-read action marked `independence: required` stays refused for them.
- **AC-14** Given an engagement whose client is not an attest client (a CAS close, a tax return), then no independence condition applies to reads, writes, assignment or sign-off for any member; confirmation is still requested on assignment and recorded.
- **AC-15** Given a firm with `g2_blocks_view` on, then pending members of an attest client's engagement also lose content reads (`authorise` and `visible()` agree). The setting is stricter only: no setting, gate policy, override or role can loosen AC-13.
- **AC-16** Given any consumer asking whether a person is cleared, then the one answer is the engagements module's confirmation lookup (`register_independence` for `authorise` and `visible()`, `engagements.api.independence_cleared` for P-04 and assignment): cleared means a confirmation by that person for that engagement that no later decline supersedes; unregistered or unknown answers not cleared (fail closed). Firm roles, client roles and break-glass support are not bound; an agent is bound through its initiator.

### Story 5: confirmation and the conclusion (CLI-08 a, b, e, f)
- **AC-17** Given a team member, when they tick the three statements and confirm, then only their own confirmation is written (409 `not_self` for anyone else), with the statement version, and `independence.confirmed` is audited with them as actor; when they decline with a note instead, then the note is sealed, the engagement partner is notified and the member stays not cleared (DF-06).
- **AC-18** Given the engagement partner with fresh MFA, when they conclude Independent, Independent with safeguards (safeguards text required) or Not independent, then one insert-only conclusion row is written (`actor_kind = 'human'` CHECK, `supersedes_id` for a later conclusion), `independence.concluded` is audited, and G2 is met only for the first two options.
- **AC-19** Given any of: a member not confirmed, a conflict result not cleared, or (attest client) no SKE designee or a NAS row without a decided evaluation, then the conclusion answers 409 `independence_preconditions_unmet` with each blocker as an identifier fact.
- **AC-20** Given the agent or a system principal, then `independence.confirm` and `independence.conclude` are denied at the matrix, `require_live_human` and the CHECK layers (INV-1).

### Story 6: NAS evaluation and the SKE designee (CLI-08 c; ADR-164 items 6, 7)
- **AC-21** Given an attest client, then every nonattest service the firm provides to it (a CAS close, tax preparation, advisory, readiness work) is a NAS row on its attest engagement, prepared by a partner or manager (`nas.evaluate`), with the evaluation decision reserved to the engagement partner and the SKE designee recorded; rows and their events are insert-only. When readiness is the client's only attest-family engagement, it needs no NAS row.
- **AC-22** Given an attest client's engagement with no SKE designee contact (`engagement_contacts`, DEC-63), then NAS evaluation and the conclusion are refused; given a non-attest client, then the screen reads "Non-attest client: no SKE designation required" and no NAS row is asked for.

### Story 7: conflict checks and screening (CLI-06 a, h)
- **AC-23** Given intake names (at most 50), when a conflict check runs, then it searches clients, client entities, contacts, relationships and engagement counterparties as a system principal over metadata only, synchronously with a 2-second statement timeout, and stores the names sealed.
- **AC-24** Given a match on a client the person running the check is walled from, then the result is `{redacted: true, match_kind}` rendered "Match on a restricted client", with no name, no link and no count beyond that row; no response anywhere has a hidden-by-wall field (DEC-43, DEC-64, R-14).
- **AC-25** Given a hit, then only a manager or partner can clear it, with an assessment code (`clear`, `same_family_not_adverse`, `not_adverse`, `counterparty_review`, `conflict`) and a reason; the clearance is an insert-only event audited as `conflict.cleared`; the agent and system are denied `conflict.clear`.
- **AC-26** Given a screening list (OFAC SDN, adverse media, restricted entities), then its result is recorded by a person (`no_match`, `match`, `not_applicable`) with an optional evidence link, insert-only, and the row reads "Recorded by ‹person›"; nothing is looked up automatically.

### Story 8: rotation (CLI-08 d)
- **AC-27** Given the rotation tab, then each person's years served derive from the `prior_engagement_id` chain and their role history (never a typed number), and a familiarity flag appears when years served reach the firm setting `rotation_review_years` (int, seed 7).

### Story 9: breaches (CLI-08 g)
- **AC-28** Given a logged breach, then the G2 banner stays until its evaluation, TCWG communication and remediation are each recorded as insert-only events by a partner, manager or quality partner (`independence.breach_manage`); the breach log has no update or delete.

## 6. Behaviour and flows
| From | Event | To | Who can trigger |
|---|---|---|---|
| acceptance `draft` | send to partner (every manual check complete) | `awaiting_partner` | `acceptance.prepare` |
| acceptance `awaiting_partner` | decide accept / accept with conditions | `decided` (engagement Prospect → Accepted, G1 met) | engagement partner, fresh MFA |
| acceptance `awaiting_partner` | decide decline | `declined` (engagement → Declined) | engagement partner, fresh MFA |
| confirmation `requested` | confirm / decline | `confirmed` / `declined` | the member, for themselves |
| G2 unmet | conclude independent (with safeguards) | G2 met | engagement partner, fresh MFA |

## 7. Domain and data changes
P-07 §4.2: M5 `acceptance_v2` (P-07-T35), M6 `conflict_checks` (T36), M7 `independence_v2`
(T41). G2 v2 (P-07-T24) adds no table: the firm setting `g2_blocks_view` joins the registered
`firm_setting_values` keys (CHECK widened). Insert-only: flags, decisions, condition events,
risk-partner reviews, conclusions, NAS events, conflict result events, screening records, breach
events. Free text (rationale, notes, safeguards, evaluations, reasons) is sealed per tenant.

## 8. Interfaces
P-07 §4.3 "Engagements" and "Clients" (acceptance, independence, NAS, breaches, conflict checks,
screening); error codes in §4.3. `engagements.api.independence_cleared(tenant, engagement_id,
user_id) -> bool` and `engagements.api.acceptance_decided_at(engagement_id)`.

## 9. Authorisation and tenancy
- **Tenant scoping:** `tenant_session(ctx)` on every read and write; every table through `tenant_table()` with forced RLS.
- **Who can do what:** `docs/architecture/permission-matrix/engagements.yaml` (acceptance, independence, NAS, breaches) and `organisations.yaml` (conflicts, screening); every decision and confirmation denies agent and system and is in `docs/architecture/human-only-actions.yaml`.
- **Ethical walls / independence constraints:** walled clients answer 404 everywhere; conflict matches on them are redacted (AC-24). G2 v2 per AC-13 to AC-16.
- **Client-side access:** none; no client role holds any action in this spec.

## 10. AI behaviour
N/A in this spec: no model call. The pre-screen is deferred (DEC-64).

## 11. Integrations
None. Screening is recorded by a person; no list provider is called.

## 12. Edge cases and failure modes
- A member removed from the team after confirming: their confirmation stays on record and clears nothing.
- A client that becomes an attest client mid-engagement: G2 v2 applies from the next request (the flag is read at request time, ADR-164 item 1).
- A second conclusion after a breach: a new row with `supersedes_id`; the earlier row is never changed.
- A decision attempt with a stale record version: 409 `stale_version`.

## 13. Security and privacy
- **Data classification:** names confidential; rationale, notes, safeguards and reasons confidential and sealed; codes and identifiers internal.
- **Threats considered:** wall disclosure through conflict results (redacted, no counts); an agent or system deciding (four layers deny); a firm loosening G2 (stricter-only setting).
- **Mitigations:** human-only CHECKs, the banned-pattern call-site rule, redaction at the service layer, fresh MFA on decisions.

## 14. Audit trail and evidence integrity
`acceptance.*`, `independence.*`, `nas.evaluated`, `independence_breach.*`, `conflict_check.run`,
`conflict.cleared`, `screening.recorded` (P-07 §4.7), one per state change in the same unit of
work with the human actor (INV-5). Decision and conclusion rows are immutable.

## 15. Observability
Counts of refusals by gate (G1, G2) without names; never log sealed text or matched names.

## 16. Performance and scale
Conflict check ≤ 50 names, 2 s statement timeout; teams ≤ 50 members; one grouped query per
CLI-08 summary.

## 17. UX
CLI-06, CLI-07, CLI-08, ENG-05 screen contracts (`docs/screens/`). Refusals render the C-20
not-allowed pane with the unblocking action ("Ana Cruz must confirm independence" → CLI-08).

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-10 | integration | P-07-T38 (independent suite for T35) |
| AC-11, AC-12 | integration | P-07-T14 (letter date, wizard G1) |
| AC-13 to AC-16 | unit + integration | P-07-T26 (independent suite for T24) and the identity authz allow and deny tests |
| AC-17 to AC-22, AC-27, AC-28 | integration | P-07-T43 (independent suite for T41) |
| AC-23 to AC-26 | integration | P-07-T44 (independent suite for T36) |

## 19. Rollout
- **Feature flag:** `engagements.v2` (G2 v2 semantics with ENG-05) and `engagements.acceptance_v2` (CLI-07, CLI-08 v2).
- **Migration and backfill plan:** SPEC-025's `engagement_acceptance` rows convert into records and decisions (synthetic data only); the table drops with its adapter in P-07-T59.
- **Rollback plan:** each migration is reversible under P-38; G2 v2 reverts to TASK-045's stricter read gate by reverting its commit.

## 20. Open questions
Must be empty before status is `approved`.

## 21. Future / explicitly deferred
The AI pre-screen (DEC-64, behind the data boundary); the annual firm-wide confirmation (DEC-91,
G-01); `todo.assign` refusal (P-05); GL-write and policy-principal `attest_client: deny` (P-16,
P-08).
