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
| Reject | `POST /v1/proposed-entries/{id}/reject` | `proposed_entry.reject` | 200 · 409 `entry_locked` |
| Record a client decision | `POST /v1/proposed-entries/{id}/client-decision:record` | `proposed_entry.record_client_decision` | 200 (evidence required) |
| Batch | `POST /v1/approval-batches` | `approval_batch.create` | 201 |
| Adjusted TB | `GET /v1/work-items/{wi}/adjusted-tb?layer=` | `adjusted_tb.read` | 200 |

Every operation answers 404 to a client principal, 404 with the flag off and 501
`not_implemented` until its task.
