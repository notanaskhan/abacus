---
id: RB-67
title: "Adjustments flip: proposed entries, client approvals through C18, and what never posts"
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-12-17
---
# RB-67 · Adjustments flip

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (a batch waits for a client) to SEV1 (anything written to a client's ledger) |
| Source | A-06-T37; A-06 §3; C8; DEC-2714 |

## What turns on
With the `assurance_completion` entitlement (RB-66) a firm's AUD-16 shows proposed entries,
threshold policies and named-person batch approval. Approve-and-send holds the C18 send for 10
seconds (Undo); then `deliver_proposed_entries` puts each entry before the client on its work item
(R-02-T07). Nothing is ever posted to a client system (ADR-040, `pe_posting_dormant`).

## Checks before a firm's flip
1. The firm's threshold policy is published (AUD-16 b) and names its approvers.
2. Client approvers of record are designated on the engagement (C18 decider rule).
3. `pe_posting_dormant` is set: no route posts, books or pushes an entry.

## If something goes wrong
- A send reached the wrong client: void the approval grant inside the Undo window; after it, end
  the firm's entitlement row (RB-66) and raise SEV2.
- Anything written to a client ledger: SEV1; there is no code path for it, so treat it as a breach.
