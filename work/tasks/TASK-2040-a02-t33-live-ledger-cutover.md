---
id: TASK-2040
title: A-02-T33 Live-ledger production cutover
spec: SPEC-333
acceptance_criteria: [AC-52]
risk_zone: red
status: blocked
epic: A-02
plan_key: A-02-T33
branch: s15c-a02-t33
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Intuit production keys in Secrets Manager, a single redirect host on the neutral portal domain,
app-assessment evidence, a connector kill switch, the adapter registered dark behind
`connections.live_ledger`; production refuses fake providers at boot, the adapter is registered but
dark, and a staging drill shows the kill switch stopping pulls within one minute.

## Plan (red: written before the code)
- `kernel.config`: `_live_ledger_host_matches_environment` (production refuses the sandbox host and
  needs `connections_redirect_base_url` with QuickBooks; other environments refuse the live host);
  the new setting; the fake connector's local-only rule already stands.
- `connections.connect._redirect_uri`: the registered host when set, else `app_base_url`.
- `connections.pipeline.pull_raw`: a networked provider's pull checks `connections.live_ledger`
  fresh and ends `connector_paused` before credentials or the provider.
- Infra (staging): `abacus/staging/qbo` secret; mapped into the API and worker only with
  `qbo_enabled` (default false).
- `docs/ops/live-ledger-cutover.md`: guarantees, cutover steps, the drill and its record.
- SPEC-333 AC-52; tests `unit/kernel/test_a02t33_live_ledger_settings.py`,
  `unit/connections/test_a02t33_kill_switch.py` (run at the end review).
- Rollback: revert; the flag default (off) keeps the connector dark either way.

## Blocked on
Intuit's production app assessment and keys (human), the production compute stack, and the
sandbox secret plus `qbo_enabled` on staging for the drill.

## Progress log
- 2026-10-30: guards, redirect setting, kill switch, staging secret wiring, runbook and tests built.
