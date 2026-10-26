---
id: SPEC-319
title: "Requests and binders engine (C5 v1, binders and requests half): binder lifecycle, request lifecycle v2, portal mark-done, ignore, upload intents and client withdrawal"
status: approved
owner: notanaskhan
risk_zone: red
related_adrs: [ADR-005, ADR-139, ADR-140, ADR-161, ADR-162]
related_specs: [SPEC-032, SPEC-042, SPEC-306]
created: 2026-10-22
updated: 2026-10-26
---

> **Final (P-06-T27, 2026-10-26).** Written as an outline with the C5 v1 stub (P-06-T01, TASK-415)
> and grown story by story; this spec now replaces the epic as the source for P-06's behaviour.
> Shapes, routes and error codes are the contract's (`docs/contracts/c5-requests-binders.md`);
> each AC names the suite that proves it (§18). What P-06 left open is listed in §20 and §21 and
> in the hand-off (`work/tasks/TASK-1311-p06-docs-closeout.md`), never folded into an AC.

## 1. Summary
Binders become many `request_lists` per work item with a lifecycle (Draft, Published, Unpublished, Complete, Closed); requests get the DEC-09 status set, the client's own words and a composer with a recipient preview; the client can mark a binder done, ignore a request with a reason, announce an upload in progress and withdraw an upload the firm never accepted. A named person publishes, sends, returns, delegates and accepts; the agent never does (INV-1).

## 2. Problem and context
The repo has one request list per engagement and a PBC board. BND-01, BND-02 and SHL-14 (P-06) need binders per work item (DEC-31), a request lifecycle and portal actions, and A-01, R-01, T-02 and C-01 build on the same schema. C5 freezes S3 (Fri Dec 11, 2026).

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engagement partner, manager | Create, publish, unpublish binders; waive requests |
| Senior, `client_service` | Create and publish binders when the firm setting allows (DEC-38) |
| Staff | Send and return requests; accept evidence when `staff_can_accept_evidence` is on (DEC-37) |
| Client admin, client contributor | Mark a binder done, ignore a request with a reason, announce uploads, withdraw unaccepted uploads |
| Agent | Drafts requests only; denied every human-only action |

## 4. Goals and non-goals
**Goals:** the C5 v1 routes, models and matrix rows (§8); the lifecycles in §6; flag `binders.engine`.

**Goals (added as the family grew):** follow-ups v2 (Story 5, P-06-T14) and the SHL-20 screening aggregate (Story 6, P-06-T15, T20, T22) in C5 v1.2; the four screens (Story 7).

**Non-goals:** SHL-14 c (A-03); portal screens (R-01); P-40 client-scoped files (N-01); SSE (P-10).

## 5. User stories and acceptance criteria
### Story 1: the C5 v1 stub (P-06-T01)
- **AC-1** Every C5 v1 route in §8 exists with exactly one matrix action, documents 404 and 501, and every client-visible effect (publish, send, return to client, withdraw) requires an `Idempotency-Key` header.
- **AC-2** Binder and request statuses in every C5 model are C2's generated enums (`BinderStatus`, `RequestStatus`); every field carries a classification tag (ADR-031).
- **AC-3** The human-only actions (`binder.create`, `binder.update`, `binder.publish`, `request_item.send`, `request_item.return`, `request_item.delegate`, `evidence.accept`, `evidence.reject`) deny the agent; the client actions (`binder.mark_done`, `request_item.ignore`, `evidence.withdraw`) grant no firm role and deny the agent; the ignore requires a reason; publish names only registered firm-setting keys.
- **AC-4** With `binders.engine` off every C5 route answers 404; with it on, a stubbed route answers 501 `not_implemented`.

### Story 2: binders (P-06-T07, T11; epic Stories 1.1 to 2.1)
- **AC-5** Publishing before G3 answers 409 `binder_gate_unmet`, except an `intake` binder; missing due dates answer 422 `due_date_required` with the item IDs.
- **AC-6** Publish moves Draft or Unpublished to Published, sends draft client-visible requests, dispatches email only after the 10-s Undo window (ADR-161), and a retried request with the same `Idempotency-Key` sends nothing twice.
- **AC-7** Unpublish without a reason answers 422 `reason_required`; with one, client principals get 404 for the binder and its requests at once (INV-4).
- **AC-8** "Duplicate as pt 2" creates an empty Draft with `part = max + 1`, the same recipients and categories (OQ-7).
- **AC-9** The client's mark-done moves Published to Complete with the open count; a firm return or new send moves it back to Published; a terminal work-item transition closes it (`binder.closed`, actor `system`).
- **AC-10** The index lists, counts and totals only binders visible to the caller; no field reveals a hidden count (INV-3, DEC-43); the Brightwater Hale tiles foot to 241.

### Story 3: requests (P-06-T10; epic Stories 3.1 to 4.3, 8.1)
- **AC-11** Send needs a due date (422 `due_date_required`), passes the scope check (409 `out_of_scope`) and refuses unchanged model-drafted wording while P-25 is off (409 `model_text_not_permitted`, DV-11); `sent_by` is always a person (INV-5).
- **AC-12** The client's Ignore records `client_ignored_at` and the reason and leaves the status `requested` (OQ-3); return-to-client clears it; waive sets `not_applicable` with a reason.
- **AC-13** Delete works only on never-sent Drafts (409 `request_already_sent`); a delegated third party sees exactly one request.
- **AC-14** Upload intents expire after 90 s and feed "Uploading n files…"; the live poll returns intents, inbox waiting counts and screening-running flags.

### Story 4: client withdrawal (P-06-T18, T19; ADR-162)
- **AC-15** A never-accepted client upload is void and hidden from firm reads and agents at once; an ever-accepted version answers 409 `evidence_accepted`; another contributor's upload 403 `not_your_upload`; erase happens after 30 days unless held, and never when no hold check is registered.

### Story 5: follow-ups, drafted by the platform, sent by a person (P-06-T14; DEC-74, DEC-220)
- **AC-16** Drafting over binders or requests writes one follow-up per client contact per engagement from the published Reminder template (C16, in the database), listing each open client-visible request once and never one already waiting in a draft to that contact; nothing is sent.
- **AC-17** A person edits the body before sending; the edit is sealed and fingerprinted; a sent follow-up can't be edited (409 `follow_up_already_sent`).
- **AC-18** Send is scope-checked (409 `out_of_scope`, nothing written), held by an approval grant until the 10-s Undo window ends, and the email leaves once; Undo within the window sends nothing (later, 409 `undo_window_closed` / `effect_started`); the audit trail and the message name the person as sender (INV-5).
- **AC-19** No code path lets the agent principal send: `follow_up.send` denies the agent at every autonomy level, the P-4 tick only drafts, `follow_up.sent` is human-only in the database, and the recorded engagement-agent histories replay unchanged.
- **AC-20** Partners, managers, seniors, staff and `client_service` may draft and send; reviewers may not send.

### Story 6: the evidence screening aggregate (P-06-T20; DEC-48, DEC-324; epic Stories 5.1 to 5.3)
- **AC-21** Code composes a request batch's aggregate as a `request_batch` row of `screening_results` (`created_by_kind = system`). Each change supersedes the item's previous row with `batch_no + 1`; an unchanged composition writes nothing; no row is updated; the database refuses an aggregate from an agent or a person, and every 0010 rule still holds for `version` rows.
- **AC-22** Any flag makes the batch flagged, both checks passing make it passed, anything else is not screened. "Right document" comes only from shown, code-verified reviewer flags (`irrelevant`). "Right period" comes only from code: the document's dates against the request's period, else the `wrong_period` check. No model output changes the period verdict, and no aggregate path writes a request's status or a review decision.
- **AC-23** A withdrawn version is left out of the aggregate when it is composed and when the card is read; a withdrawal recomposes every batch that held it.
- **AC-24** `GET …/screening` answers 404 with `screening.card` off; it is a firm reviewer's read (`upload_review.read`; clients and `client_service` refused); it carries no confidence; its file flags name the file, the reason (`wrong_document`, `wrong_year`) and the verified citation as region.
- **AC-25** Rerun answers 202, starts reviews only for current versions without a completed review under the reviewer's current prompt, recomposes, and answers 409 `screening_running` while a review of the files runs.
- **AC-26** Feedback is a person's insert-only row on an aggregate (a thumbs-down without a reason is 422; the agent is denied; a per-version result answers 404); the note is sealed; the card shows the viewer's latest.
- **AC-27** On a `tax_return` work item at a firm that is not synthetic (no §7216 consent registration exists until C19), the reviewer makes no run and no model call, and the aggregate's model check stays not run; code checks still run.
- **AC-28** A review decision's `screening_result_id` may name only a `version` row.

### Story 7: the screens, parity and accessibility (P-06-T09, T12, T13, T16, T22, T24, T26; epic §5.5, §5.6)
- **AC-29** All 23 built artboards (BND-01 a–e, BND-02 a–g, SHL-14 a, b, d, e, f, SHL-20 a–f) are reported at Tier C (threshold 0.20, maxDiffPixelRatio 3 %); BND-01 and BND-02 are locked at Tier C; Tier D holds for the host templates; SHL-14 c is recorded as deferred to A-03.
- **AC-30** axe finds no serious or critical issue in any artboard, and the keyboard suites pass: overlays close on Escape and give focus back to their opener, the composer drawer's dirty guard asks "Discard changes?", the screening card closes on Escape back to its chip, and the feedback menu cannot send without a reason.

## 6. Behaviour and flows
**State transitions**
| From | Event | To | Who can trigger |
|---|---|---|---|
| binder `draft` / `unpublished` | publish | `published` | `binder.publish` (human) |
| binder `published` | publish Undo within 10 s | `draft` | `binder.publish` (human) |
| binder `published` | unpublish with reason | `unpublished` | `binder.publish` (human) |
| binder `published` | client mark-done | `complete` | `binder.mark_done` (client) |
| binder `complete` | firm returns or sends a request | `published` | `request_item.return` / `.send` |
| binder any non-terminal | work item terminal (C1) | `closed` | system |
| request `draft` | send | `requested` | `request_item.send` (human) |
| request `requested` | client ignore | `requested` + `client_ignored_at` | `request_item.ignore` (client) |
| request `requested` | waive | `not_applicable` | `request_item.waive` (human) |
| request `uploaded` | only fulfilment withdrawn | `requested` | `evidence.withdraw` (client) |

## 7. Domain and data changes
F-03-T14 and F-03-T15 already landed the binder columns and the request status set. P-06-T05 (`binder_engine`) adds the rest of P-06 §4.2: binder stamps, `created_from`, `template_ref`, `follow_up_override`, `closed_*`, `binder_recipients`; request `title`, `category_id`, `firm_owner_user_id`, `period_*`, `wave`, `kind`, `source_tag`, `supports_ref`, `linked_ref`, `drafted_*`, `sent_by`, `deleted_*`; `request_delegations`; UNLOGGED `request_upload_intents`; `binder_activity`. P-06-T18 adds `evidence_withdrawals` and `evidence_object_keys`. No migration in the stub.

## 8. Interfaces
The routes, models and actions are listed in `docs/contracts/c5-requests-binders.md` §2 and §3 (code: `backend/src/abacus/modules/requests/contract.py`, `backend/src/abacus/modules/evidence/contract.py`).

## 9. Authorisation and tenancy
- **Tenant scoping:** `tenant_session(ctx)` on every read and write; binders and requests through `visible()` (F-03-T27).
- **Who can do what:** `docs/architecture/permission-matrix/requests.yaml` and `evidence.yaml` (C5 rows). Conditions only narrow (DEC-132); the per-kind refinements (`not_offshore` on tax-return binders, the OQ-1 preparer path, DEC-136) are applied when the routes go live.
- **Ethical walls:** walled binders are absent and answer 404 (INV-3).
- **Client-side access:** published binders in scope, client-visible non-draft requests, a delegate's one request (INV-4).

## 10. AI behaviour
N/A in this family: no model call. Agent drafts carry `drafted_by_run_id`; sending them is a person's act (INV-1, DV-11).

## 11. Integrations
Email through C16 templates after the Undo window (P-04-T10 grants, P-06-T06 delivery). Idempotency through `kernel/idempotency` (P-06-T06).

## 12. Edge cases and failure modes
- Publish retried with the same key: the stored response, no second email.
- Undo after 10 s: 409 `undo_window_closed`.
- Withdraw racing an accept: the first commit wins, the other answers 409.
- Upload intent never refreshed: it expires after 90 s.

## 13. Security and privacy
- **Data classification:** names and wording confidential; identifiers and codes internal; no Restricted field in list payloads; no TIN anywhere.
- **Threats considered:** client strings are hostile (ADR-052); the agent cannot reach a human-only action (INV-1); `client_service` sees status and file names, never content (DEC-20).

## 14. Audit trail and evidence integrity
The audit events in the contract doc §7, identifiers only; the human actor on every client-facing effect (INV-5). Evidence stays immutable except the one ADR-162 exception.

## 15. Observability
Metrics: publish and send counts, Undo rate, idempotent replays, withdraw and erase counts. Never log client wording.

## 16. Performance and scale
BND-01: 241 binders per season per firm in the seed; keyset pages of 50 (max 200). The live poll every 5 s while visible.

## 17. UX
BND-01, BND-02, SHL-14 and SHL-20 screen contracts (`docs/screens/`); flag off shows F-05's flag-off ViewState.

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1 to AC-4 | unit (contract) | `backend/tests/contracts/c5_requests_binders/test_c5_stub.py` |
| AC-5 to AC-9 | integration | `backend/tests/integration/test_binder_lifecycle.py` (P-06-T07) |
| AC-10 | integration, golden | `backend/tests/integration/test_binders_index.py`, `test_binders_index_e0.py` (P-06-T11; the E0 tiles foot to 241); `test_p06t29_binder_goldens.py` (P-06-T29) |
| AC-11 to AC-14 | integration | `backend/tests/integration/test_request_lifecycle.py` (P-06-T10) |
| AC-5 to AC-14 | integration (independent) | `backend/tests/integration/backfill/test_p06t17_binders_requests.py` (P-06-T17, TASK-1140) |
| AC-15 | integration, workflow replay | `backend/tests/integration/backfill/test_p06t19_withdrawal.py`, `test_p06t19_security_review.py`, `test_p06t18_detached_keys.py`, `test_p06t23_withdrawal_race_and_screening_rows.py` (P-06-T23); `backend/tests/workflows/test_withdrawal_purge_replay.py` |
| AC-16 to AC-20 | unit, integration, workflow replay | `tests/unit/agents/test_follow_up_drafts.py`, `tests/unit/communications/test_follow_up_templates.py`, `tests/integration/test_follow_ups_v2.py`, `tests/integration/test_screening_return.py`, `tests/workflows/test_engagement_agent_replay.py` (P-06-T14); `tests/integration/backfill/test_p06t23_follow_ups_v2_independent.py` (P-06-T23) |
| AC-21 to AC-28 | integration, contract | `tests/integration/backfill/test_p06t20_screening_aggregate.py` (P-06-T20), `test_p06t23_withdrawal_race_and_screening_rows.py` (P-06-T23); `tests/contracts/c5_requests_binders/test_c5_shl20_family.py` |
| AC-29 | visual (Playwright) | `apps/web/e2e/parity/screens.spec.ts` over each contract's Parity table; `e2e/visual/tier-d.spec.ts`. Not yet measured: `docs/quality/parity-P-06.md` |
| AC-30 | component (vitest), Playwright | `apps/web/src/screens/{BND-01,BND-02,SHL-14,SHL-20}/*.keyboard.test.tsx` (P-06-T26); axe in `apps/web/e2e/screens/{BND-01,BND-02,SHL-14,SHL-20}.spec.ts` (not yet run, `docs/quality/parity-P-06.md`) |

## 19. Rollout
- **Feature flags:** `binders.engine`, `screening.card` and `evidence.withdrawal`, each default off and expiring 2027-04-21 (DEC-137); the renewal plan is `docs/plan/status/flag-renewals-2027.md` (P-06-T27).
- **Rollback:** the stub only adds routes behind the flag and matrix rows; revert the commit.

## 20. Open questions
- [ ] OQ-1 mechanism (DEC-136): the plan's option is decided (the return's preparer may publish a `tax_return` binder), but the derived grant that would widen `binder.publish` is not built; `binder.publish` has DEC-38's cells only.
- [ ] The live poll's inbox-waiting and screening-running facts: no module registers `requests.register_live_facts`, so they read 0 and false on the live stack (DEC-158).

## 21. Future / explicitly deferred
SHL-14 c (A-03), SSE (P-10), the per-binder follow-up override write (its route still answers 501), `requests.api.awaiting_review_count` (I-01), the model drafter (N-03, P-25).
