---
id: TASK-2232
title: N-02-T22 independent AC tests for T18-T20 (DocuSeal)
spec: SPEC-381  # N-02 §3.5; ADR-078 independent tests; ADR-342
acceptance_criteria: [AC-16]
risk_zone: red
status: done
epic: N-02
plan_key: N-02-T22
branch: s17-n02-t22
created: 2026-10-30
updated: 2026-11-01
---

## Objective
Independent acceptance tests (ADR-078) for N-02-T18 to T20 on the DocuSeal path: no provider write
without a consumed grant, retries re-read before re-writing, the egress allowlist and kill switch,
forged and replayed provider calls refused, webhooks never changing state without a poll,
validation computed by code, no SMS for the e-file family, Send and Undo human-only, and the
interception harness over W7.

Acceptance (backlog row): "The suite passes and fails if an agent principal or an unconsumed grant
reaches the adapter."

## Plan (red)
- Unit (`tests/unit/connections/test_n02t22_signatures_independent.py`, beside the W7 harness):
  lost-answer retry creates once; refused API and file hosts; kill switch builds nothing and reads
  no secret; a whole envelope through httpx's real transports is HTTPS to declared DocuSeal hosts
  with writes on the API host only and the key nowhere else; forged, moved, edited and stale
  webhooks refused; the builder imports no model; no SMS anywhere; Send, Undo and the send check
  refuse agent, system and support.
- Integration (`tests/integration/backfill/test_n02t22_send_independent.py`): the send activity
  with no, an unconsumed, a voided or another approver's grant never reaches the adapter; a grant
  consumed for its sender sends once; an agent or the system can never become the sender; a
  webhook hint changes nothing until the poll; the database refuses `sms_code`.
- **Gap found and fixed:** the send activity never checked the grant, and nothing moved a sent
  draft to Sent (the activity returned on `draft`, so a real send never reached the provider). The
  activity now reads identity's new `consumed_grant_approver` (the newest consumed, unvoided
  `envelope.send` grant on the envelope) and writes the provider only when its approver is the
  envelope's `sent_by`; otherwise `envelope.send_refused` and nothing leaves. The provider's id
  and Sent are set together. Seeds of the T14 and T16 tests now carry the consumed grant a real
  send leaves.

## Progress log
- 2026-10-30: built (DEC-1284). Tests written, run at the end review.
- 2026-11-01: merged to main in #891 (c6c378126).
