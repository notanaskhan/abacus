---
id: TASK-5901
title: QuickBooks revoke really ends the grant; intuit_tid survives the log's backstop
spec: SPEC-000  # row (TASK-5901): A-02-T26 (connector), DEC-515 M1, F-09-T05
acceptance_criteria: [AC-1]  # a live sandbox revoke returns 200 and the revoked token then fails; no refusal reads as revoked; every intuit_tid is logged intact
risk_zone: red
status: in-review
branch: qbo-revoke-tid
created: 2026-11-05
updated: 2026-11-05
---

## Objective
Fix two defects the abacusv2 sandbox check found (DEC-2901).

## Scope
**In**
- `quickbooks_online.revoke`: JSON body, as Intuit's SDKs send it; only a 200 is success; 429 and
  5xx are `Unavailable`; anything else raises `revoke_refused`, which `grants._revoke` records
  as `refused`.
- `kernel/egress.py`: `EgressClient.request` gains `content` (raw body). The read-POST check is
  unchanged. The fakes take the new keyword.
- `tid_for_log`: the tid as one hex run, opaque to `kernel.tin_patterns`. The backstop is
  unchanged.

**Out**
- Telling an already-revoked token from any other 400: Intuit's body has no OAuth error code
  (`error` logged null), so nothing to read.

## Plan
- [x] Plan approved by human (Ayush, 2026-11-05: "Yes, fix both")

1. [x] Tests in `tests/unit/connections/test_qbo_connector.py`.
2. [x] Live test on abacusv2's sandbox tokens.

Rollback: revert the commit.

## Progress log
- 2026-11-05: found when the Quick Start revoke got a 400 and the tool printed `revoked`.
  Intuit's Python and JS SDKs send JSON; ours sent a form body, so disconnects have probably
  never ended a grant at Intuit, while the audit said `revoked`. No real firm was connected.
- Live, 2026-11-04 22:48 UTC: revoke 200; the same token again 400 (no OAuth code, now
  `revoke_refused`); refreshing the revoked token 400, `token_expired`.
- Ruff, pyright, lint-imports; connector, connection, egress, logging, banned-pattern and C20
  suites: 3,891 passed.
