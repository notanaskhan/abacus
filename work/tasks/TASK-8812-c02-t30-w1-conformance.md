---
id: TASK-8812
title: "C-02-T30: Connector conformance for the W1 writer (fake per PR, sandbox nightly)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-c02t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T30
---

## Objective
The suite passes against the fake in stage 2 and against the sandbox nightly, and a drift between the two opens a ticket.

## Done
- backend/tests/connectors/quickbooks_online/test_w1_writer_conformance.py: create + read-back, closing date set and read, inactive account refused before a write, 429/401 codes, golden request body (golden/w1_journal_entry_aje01.json), real-host block on the write lane; targets fake and sandbox (nightly connectors-nightly picks them up by -k), outcomes to W1_DRIFT_REPORT for the drift job
- HttpQboTransport (Intuit v3 over EgressClient; requestid = sha256 digest of the idempotency key)
- kernel egress W1 write lane: configure_write_egress + EgressClient.write, empty unless a released entry or the sandbox test opens it

## Progress log
- `2026-11-20` — Plan (red): kernel lane, live transport, suite; rollback revert. Production registration of the live transport and the lane from released entries is C-02-T50 (after the deferred pen test, DEC-1389). Runs at the end pass.
