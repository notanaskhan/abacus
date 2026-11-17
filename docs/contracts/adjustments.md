# C8 · Adjustments v1 — proposed entries, approval batches, the adjusted TB

| Field | Value |
|---|---|
| Register row | C8 in `docs/contracts/README.md` |
| Owner | adjustments (A-06; SPEC-642) |
| Status | stub (A-06-T05, 2026-11-01; DEC-1965); **v1 frozen Fri Oct 1, 2027** per the register; live with A-06-T09 and T10 |
| Code | `backend/src/abacus/modules/adjustments/contract.py` |
| Tests | `backend/tests/contracts/c08_adjustments/` (A-06-T06, AY's consumer suite) |
| Flag | `adjustments.entries` (default off; DEC-137, expires 2027-04-30) |
| Consumers | AUD-16 b, b2, c, d; EBP-06 (AJE layer, AJE-1 pill); T-05; C-02; A-09 (eliminations); AUD-20 (Final layer) |

## Rules
- **Nothing is posted** to a client system: no route, workflow or adapter exists for it, and the
  database refuses Posted, Failed post and Reversed (`pe_posting_dormant`) until a C-02 migration
  under an accepted ADR P-16 drops it (ADR-040, DEC-69).
- An attest client's entry is always Review required (CHECK); every approval, batch, send and
  recorded decision is a named person's (insert-only, human-only decisions and batches).
- An entry balances at commit (`unbalanced_entry`); its lines lock once it is approved
  (`entry_locked`); a correction is a new entry.
- Client wording comes from the firm's approval template (database content), never a model
  (DEC-79); a send holds its client-visible effect for 10 seconds (Undo, DEC-24).

## Operations
| Operation | Method and path | Action | Answers |
|---|---|---|---|
| Entries | `GET /v1/work-items/{wi}/proposed-entries?kind=` | `proposed_entry.read` | 200 · 404 off |
| Propose | `POST /v1/work-items/{wi}/proposed-entries` | `proposed_entry.create` | 201 · 409 `unbalanced_entry` |
| Approve and send | `POST /v1/work-items/{wi}/proposed-entries:approve-and-send` | `proposed_entry.send_to_client` (fresh MFA) | 201 with `undo_until` |
| Send preview | `GET /v1/work-items/{wi}/proposed-entries:send-preview?entry_ids=` | `proposed_entry.read` | 200 recipient and template wording (AUD-16 O3; A-06-T22 stub, DEC-2254) · 501 |
| Reject | `POST /v1/proposed-entries/{id}/reject` | `proposed_entry.reject` | 200 · 409 `entry_locked` |
| Record a client decision (emits `proposed_entry.client_decided`; C16 `proposed_entry_client_responded` to the partner and managers) | `POST /v1/proposed-entries/{id}/client-decision:record` | `proposed_entry.record_client_decision` | 200 (evidence required) |
| Batch | `POST /v1/approval-batches` | `approval_batch.create` | 201 |
| Adjusted TB | `GET /v1/work-items/{wi}/adjusted-tb?layer=` | `adjusted_tb.read` | 200 |

Every operation answers 404 to a client principal, 404 with the flag off and 501
`not_implemented` until its task.

## Screen contract (A-06-T38)
AUD-16: `docs/screens/AUD-16.md` (artboards, deviations, consumer notes).

## C8 v1.1 · eliminations (A-09-T03; SPEC-658 F4; DEC-5039)
Additive. A `proposed_entries` row with `kind = 'elimination'` carries `consolidation_id` (required),
`posting_target = 'consolidation_layer'`, a `display_code` (E1a…) and `proposed_by_run_id`; each line
carries `client_entity_id` and `consolidation_level`. Routes (stubs in
`assurance/group_contract.py`): GET/POST `/v1/consolidations/{cid}/eliminations`, PATCH
`/v1/proposed-entries/{id}/elimination`, POST `…/elimination/approve` (409 `unbalanced_entry`) and the
per-item POST `/v1/consolidations/{cid}/eliminations/approve`, POST `…/elimination/apply` and
`…/elimination/reject`, POST `/v1/consolidations/{cid}/eliminations/propose` (202). Actions
`elimination.read`, `.edit`, `.propose_run`, `.approve`, `.post` (A-09-T02).

**The CHECK clause C-02 must keep (A-09-T10):** posted, failed_post and reversed are refused **unless**
`kind = 'elimination' AND posting_target = 'consolidation_layer'`; C-02's W1 migration extends this
clause and never replaces it (an AC test fails if the elimination clause disappears).
Fixture footing: E1a 20,000,000 · E1b 26,000,000 · E2 18,000,000 · E3 240,000 · E4 2,400,000 · E5
1,200,000 = 67,840,000 Dr = Cr; the eliminations column on assets totals (48,640,000).

## C8 v2 · Posting (C-02-T06, 2026-11-17; SPEC-700; ADR-344; DEC-5505)

| Field | Value |
|---|---|
| Status | stub; **v2 frozen Fri Sep 15, 2028** per the register |
| Code | `backend/src/abacus/modules/adjustments/posting_contract.py` (`posting_router`) |
| Flag | `adjustments.posting` (default off; off: 404; on: 501 until C-02-T12, T13, T18, T19, T22) |
| Consumer tests | `backend/tests/contracts/c08_adjustments/test_c02t08_posting_consumer.py`, `apps/web/src/screens/CLS-07/contract.test.ts` (C-02-T08) |
| Callers | CLS-07 (AY), CLS-04 "Post AJE" (a batch of one through CLS-07), CLS-11 batch drawer, POR-08 card B (posted refs) |

**Operations** (one action each; agent and system denied; client principals 404):

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/work-items/{wi}/proposed-entries:close` | `proposed_entry.read` | rows, tallies, class limits, approver context, `posting_enabled`, `is_attest_client` |
| `POST /v1/proposed-entries/{id}/approve` | `proposed_entry.approve` | `seen_version`; 409 `over_approval_limit`, `snapshot_changed`; `undo_until` +10 s |
| `POST /v1/proposed-entries/{id}/request-approval` | `proposed_entry.request_approval` | gate `proposed_entry_approval`, kind `entry_approval_requested` |
| `POST /v1/proposed-entry-decisions/{id}/undo` | `proposed_entry.undo_approval` | `approval_undone`, inside 10 s, before any effect |
| `POST /v1/proposed-entries/{id}/withdraw-approval` | `proposed_entry.withdraw_approval` | `approval_withdrawn`, reason required |
| `POST /v1/proposed-entries/{id}/reject-close` | `proposed_entry.reject_close` | Rejected + CLS-06 issue |
| `POST /v1/proposed-entries/{id}/record-external` | `proposed_entry.record_external` | evidence or match ref |
| `GET /v1/work-items/{wi}/proposed-entries.xlsx` | `proposed_entry.export` | Open in Excel; JE import file without W1 |
| `POST /v1/work-items/{wi}/posting-batches:dry-run` | `posting_batch.dry_run` | preflight only, no write |
| `POST /v1/work-items/{wi}/posting-batches` | `posting_batch.post` | `Idempotency-Key`, fresh MFA, 202; grant `not_before` +10 s |
| `POST /v1/posting-batches/{id}/undo` | `posting_batch.post` | voids the grant inside the hold |
| `POST /v1/posting-batches/{id}/entries/{entry_id}/retry` | `posting_batch.post` | `Idempotency-Key`; re-read then re-write |
| `POST /v1/closing-date-conflicts/{id}/ask-client` · `…/redate` | `closing_date_conflict.resolve` | POR-20 template row; re-date withdraws the approval |

**Status words** (`proposed_entry`, `posting_batch`, `closing_date_conflict`, C-02-T03): entries add `recorded_externally`; batches `proposed → posting → posted | failed_post`.
**Human-only actions:** approve, undo, withdraw, reject, record external, dry run, post, undo, retry, resolve.
**Audit events:** `entry.approved` (batch id, policy version), `entry.approval_requested|approval_undone|approval_withdrawn|rejected|posted|post_failed|reversed|recorded_externally`, `posting_batch.created|posted|failed|undone`, `closing_date.set`, `closing_date_conflict.opened|client_asked|redated|resolved`. Values stay out (DEC-60).
**Example** (Copperleaf, batch 2026-08-A): six entries, $35,300.00 = 20,020.00 + 14,900.00 + 380.00; QBO 48213–48218; closing date Aug 31, 2026. AJE-03 fails alone on "Accumulated Depreciation" inactive (CLS-07e).
