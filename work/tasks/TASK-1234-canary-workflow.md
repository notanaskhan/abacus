---
id: TASK-1234
title: CanaryWorkflow on a 15-minute Schedule and its independent AC tests (Q-01-T30, Q-01-T58)
spec: SPEC-050
acceptance_criteria: [AC-21]
risk_zone: red
status: done
epic: Q-01
plan_key: Q-01-T30; Q-01-T58
branch: s8b-platform-ops
created: 2026-10-25
updated: 2026-10-25
---

## Objective
Q-01 F6 and §4.5: `CanaryWorkflow` (`canary:<tenant>`; a Schedule every 15 minutes; time_sensitive) runs as the canary staff identity on "Canary & Co" (`firms.synthetic = true`): it creates a request item, uploads a synthetic PDF, waits for scan, extraction and preview, runs the screener on the route the environment's boundary allows and fails the run unless every flag it gets back carries a code-verified citation or is shown Uncited (INV-2), observes the outbox event, and sends a reminder to the SES simulator address. Results go to CloudWatch (a metric) and a Better Stack heartbeat; two consecutive failures page. T58: "the canary fails a run with an uncited flag, writes no row or object outside synthetic tenants, and pages on the second consecutive failure only" (and the boundary-appropriate route).

## Plan (red zone)
- **Order (ADR-078 in a solo lane):** T58's acceptance tests are written first from the F6 text (`tests/integration/test_q01t58_canary_independent.py`), fail on today's code (no canary), then T30 is built until they pass unedited. Same session, so independence is nominal; recorded for the main session.
- **Kernel:** `kernel.dispatch.schedule_results(schedule_id, exclude=..., limit=...)`: the results of a Schedule's recent runs, newest first (None for a run that did not complete). The canary's report step reads the previous runs through it, so paging needs no table and writes no row.
- **Platform module:** `platform/canary.py` (the `CanaryProbe` port and `configure_canary_probe`; the `Heartbeat` port with `HttpHeartbeat` and `configure_heartbeat`; the pure checks `inv2_violations`, `expected_route`, `consecutive_failures`, `should_page`; the activities `canary.prepare`, `canary.create_item`, `canary.upload`, `canary.wait_processing`, `canary.screen`, `canary.observe_outbox`, `canary.send_simulator`, `canary.report`; the metric `abacus.canary.run`); `abacus/worker/canary_probe.py` (`ServiceProbe`, beside the worker because `platform` may depend on identity only, BOUND-002 over `requests.api.add_request_item`, `evidence.api.upload`, evidence processing state, the reviewer's run and raw flags through `agents.api`, the outbox row through `kernel.uow`, and `communications.api.send_email`); `CanaryWorkflow` in `platform/workflows.py` with its types in `workflow_types.py`; `WORKFLOWS` (time_sensitive) and `schedules()` in `api.py` (the canary Schedule exists only when `canary_tenant_id` is set).
- **Settings:** `canary_tenant_id`, `canary_staff_user_id`, `canary_engagement_id` (internal), `canary_heartbeat_url` (restricted; never logged).
- **Synthetic only:** `canary.prepare` refuses (non-retryable `CanaryNotSynthetic`) unless the firm is synthetic and the staff member is an active member; nothing else runs. The probe's every write is in that firm's context.
- **Paging:** a pass beats the heartbeat; the second consecutive failure (this run and the one before) calls the heartbeat's fail URL once; the first failure and the third onward call nothing (the incident is open until a pass). Better Stack's heartbeat period is 15 minutes with a grace of at least 20, so a single missed beat never pages by itself (infra to-do).
- **Tests:** T58 file above (workflow on a real Temporal dev server with a fake probe and a recording heartbeat; the real `ServiceProbe.prepare` against Postgres for the synthetic refusal); `tests/unit/platform/test_canary_checks.py` (pure checks); `tests/integration/test_canary_probe.py` (the service probe's steps against Postgres and the S3 gateway); `tests/workflows/test_canary_replay.py` with `canary-v1-passed.json` and `canary-v1-failed.json` recorded by `abacus_tools.workflows.record_canary`; the platform workflow inventory extended.
- **Rollback:** revert; delete the `canary:<tenant>` Schedule with `abacus_tools.schedules delete`.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: T58's tests written first (`tests/integration/test_q01t58_canary_independent.py`: uncited flag, unverified citation, verified-or-Uncited pass, synthetic-only stop before any write, the route per boundary (7 cases), paging on the second consecutive failure only over six Schedule-triggered runs, the real probe refusing a non-synthetic firm and writing only in the synthetic firm's rows and object keys); they failed on import before T30 existed.
- 2026-10-25: T30 built: `CanaryWorkflow` (`canary:<tenant>`, time_sensitive, every 15 minutes when `canary_tenant_id` is set), activities and checks in `platform/canary.py`, `ServiceProbe` in `abacus/worker/canary_probe.py` (configured by the worker at boot), `kernel.dispatch.schedule_results` (by run id: two runs started in one second share a workflow id, found by the paging test), `kernel.uow.relay.event_state`, `agents.api.review_citation_states`, `request_review`, `upload_review_available`, `evidence.api.upload_preview`, settings `canary_*`, metric `abacus.canary.run`. DEC-358 records the deviations (in-process identity, the fake-route screener gap, the sink, no table for paging). Histories `canary-v1-passed.json`, `canary-v1-failed.json` (`abacus_tools.workflows.record_canary`). Tests: T58 file 14 passed; `tests/integration/test_canary_probe.py` 7 passed (create, upload, wait for extraction and preview, outbox pending then published, fake-route screen, sink mail); `tests/unit/platform/test_canary_checks.py` 21 passed; `tests/workflows/test_canary_replay.py` 3 passed; platform inventory extended. Same-session authorship: ADR-078 independence is nominal for T58.
- Human to-dos (T35): create the canary staff member and engagement on the canary firm and set `ABACUS_CANARY_TENANT_ID`, `ABACUS_CANARY_STAFF_USER_ID`, `ABACUS_CANARY_ENGAGEMENT_ID` and the secret `ABACUS_CANARY_HEARTBEAT_URL` in the worker task definition; a Better Stack heartbeat with a 15-minute period and at least 20 minutes' grace; then `abacus_tools.schedules ensure`. Under `client_data` the canary firm also needs `upload_review.read` and `upload_review.request` for its staff member (manager role) and the reviewer's daily cap headroom.
