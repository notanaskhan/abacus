---
id: RB-04
title: Connector provider outage
owner: builder
owning_epic: A-02
alarms: [SLO-08, SLO-09]
last_rehearsed: never
rehearse_by: 2027-01-08
---
# RB-04 · Connector provider outage

| Field | Value |
|---|---|
| Owner | builder (written by A-02, A-02-T38) |
| Severity range | SEV3 to SEV2 |
| Linked from | SLO-08, SLO-09 |
| SLO affected | SLO-08, SLO-09 |
| Kill switches that apply | `connections.live_ledger` per firm (the live adapter's start, complete and on-demand pulls; off: 404, file imports keep working); `retrieval.auto` per firm (automatic retrievals) |
| Rehearse by | the first live connector (QuickBooks Online on staging) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

Connectors are read-only by construction (ADR-040: no write-shaped method, the write gate refuses every write, DEC-1280 opened only W7). An outage therefore never risks a client's books: it stops pulls, and snapshots already received stay (ADR-004). The daily health pass (`connection_health:platform`, A-02-T25) refreshes and checks every live connection of a provider that reaches a host; a provider error sets `needs_attention` with its code, and `pipeline.pull_raw` refuses anything that is not `active`.

## 1. Recognise it
- SLO-08 (initial pull under an hour) or SLO-09 (sync freshness) burns; retrievals and on-demand pulls (`POST /v1/engagements/{id}/connection/pulls`) end `failed` with a provider code, or many connections turn `needs_attention` with the same non-reauth code after the health pass.
- AUD-06 and POR-16 show **Needs attention** (not **Needs reauth**) on many entities of one provider at once.
- Check the provider's status page (QuickBooks Online: Intuit Developer status).
- Not this scenario: one client's expired grant (`token_expired`, `invalid_grant`: **Needs reauth**, RB-05); a validation failure on one company's data (`failed_validation`: that run's data, not the provider).

## 2. Contain
1. Nothing is written to the provider, so nothing to roll back.
2. If pulls keep failing and burning the daily retrieval cap, turn `retrieval.auto` off for the affected firms; people can still upload an exported trial balance (`ledger.import`) or GL (`ledger.gl_import`).
3. If the adapter itself misbehaves (wrong data shape, a host change), turn `connections.live_ledger` off per firm: the live start, complete and pull routes answer 404, a running pull through the live provider ends `connector_paused` within a minute (read past the flag cache, before any credential is opened; A-02-T33), and the fakes and file imports keep feeding the trial balance.

## 3. Preserve
`sync_runs` rows for the window (status, code, provider; no payloads), the health pass's `connection.health_checked` audit rows (reason codes), worker logs' error classes, and the provider's incident reference. Raw payloads never leave `pull_raw`; nothing more to keep.

## 4. Assess
- Which provider, since when, how many connections are `needs_attention` with the outage code, which firms (tenant UUIDs), which closes and engagements are inside their freshness window (SLO-09: active closes hourly, active engagements daily).
- Throttling (HTTP 429) is not an outage: lower concurrency or wait for the window; record it for the review.
- More than 20% of a firm's connections stale is SLO-09's page threshold.

## 5. Notify
Over an hour during working hours, or any active close blocked: status page component "Ledger sync", SEV2 template (`docs/ops/incident-templates.md`, QuickBooks Online sync). Firms with blocked closes get the template note that they can upload an export instead (ADR-108). Clients are not emailed: nothing is theirs to do.

## 6. Recover
1. When the provider recovers, the next health pass clears `needs_attention` (outage codes are retryable) and sets `active`; to clear sooner, the firm's **Retry** on AUD-06 (`connection.retry`) runs one retry of the newest failed run.
2. Turn `retrieval.auto` and `connections.live_ledger` back on where they were turned off.
3. On-demand pulls that failed are asked again by the person; nothing is re-pulled automatically on someone's behalf.

## 7. Verify
New retrievals and pulls succeed; the connections read **Connected**; SLO-08's and SLO-09's burn stops; the synthetic company's pull on staging passes.

## 8. Review
Typical actions: an alert on the count of `needs_attention` connections per provider and code, a lower retry budget, a provider-specific backoff, a quota request filed ahead of busy season.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
