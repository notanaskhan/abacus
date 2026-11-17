---
id: RB-92
title: "QuickBooks ledger sync (C-01): failure rate, freshness, meter budget, the kill switch and its drill, the status-page component, pre-window promotion"
owner: builder
owning_epic: C-01
alarms: [ledger-sync-failure-rate, ledger-sync-freshness, ledger-sync-meter-budget]
last_rehearsed: never
rehearse_by: 2028-08-31
---
# RB-92 · QuickBooks ledger sync (C-01)

| Field | Value |
|---|---|
| Owner | notanaskhan (`connections.ledger_sync` flag owner); ayushkbhatia for the closes side |
| Surface | `LedgerSyncWorkflow` (`ledger_sync:<tenant>`, background class), Sync now on CLS-02/CLS-04 |
| Kill switches | `connections.live_ledger` (A-02-T33) and the adapter switch `connector.quickbooks_online`: either off, every entity sync answers `connector_paused` before any Intuit call |
| Flags | `connections.ledger_sync` (owner N), `closes.engine`, `closes.portal_requests`, `closes.agent` (owner AY), renewed to Thu Nov 16, 2028 in the Thu Aug 24 train |
| Alarms | `abacus-staging-ledger-sync-failure-rate`, `abacus-staging-ledger-sync-freshness`, `abacus-staging-ledger-sync-meter-budget` (`infra/envs/staging/ledger_sync.tf`) |
| Status page | Component **QuickBooks Online sync** (SEV3 when the cause is ours; an Intuit outage links Intuit's status, never ours) |
| Pen test | POR-11 and the close routes are listed in the Sep 2028 delta scope (`docs/plan/status/pen-test-deferral.md`, C-01-T52 note; DEC-1389 defers the test itself) |

Nothing in a log line, alarm or ticket carries provider text, a token or a realm id. Quote the
client's name and the close period, never the connection's secrets.

## 1. Failure rate (`ledger-sync-failure-rate`)
1. Read the failing codes: `sync_runs.last_failure_code` per schedule (codes only).
2. `rate_limited` / `circuit_open`: Intuit throttled; the next tick waits for Retry-After. Page
   only if it persists past two hours.
3. `token_expired` / `invalid_grant`: A-02's health path moves the connection to Needs reauth
   (RB-05); the entity pauses, no action here.
4. Anything else: check the latest worker deploy; roll back if it started with it.

## 2. Freshness (`ledger-sync-freshness`)
The p95 gap between an entity's successful syncs is above 90 minutes (SLO 60 ± 15).
1. Confirm the worker's background class is running (`worker` or `worker-background`).
2. Confirm the firm's business hours (07:00–19:00 firm time by default): out-of-hours gaps are
   expected and do not page (the filter only counts successes).
3. Check the tenant workflow is alive: `ledger_sync:<tenant>` continues as new every 24 ticks.

## 3. Meter budget (`ledger-sync-meter-budget`)
A firm reached its monthly Intuit call budget: scheduled syncs paused and the firm admin was told
once. Sync now still runs. Raise the firm's budget only with F-09's tier confirmation.

## 4. The kill switch and its drill
1. Turn off `connections.live_ledger` for the firm (or `connector.quickbooks_online`
   platform-wide) on ADM-05.
2. Within one tick every entity sync logs `ledger_sync.outcome` with `outcome=paused` and no
   provider call is made (the fake QBO's request count stays flat on staging).
3. Turn it back on; the next tick syncs.
**Drill (staging, PF-X1, before Thu Aug 31, 2028):** run steps 1–3 against the fake QBO and
record the tick time, the paused count and the flat request count in this file's history.

## 5. Pre-window promotion (Thu Aug 31, 2028)
1. Every C-01 migration and the dark sync (flags off) promoted to production.
2. Flags renewed to Thu Nov 16 in the Aug 24 train.
3. Intuit tier and the per-firm call budget confirmed (F-09).
4. Alarms above applied (`terraform apply` in `infra/envs/staging`, then production).

## History
| Date | What | By |
|---|---|---|
