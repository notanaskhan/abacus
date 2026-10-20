# Service level objectives (ADR-093)

Reliability targets for Accrued. Chapter 06 §3.3 is the source. SLOs are defined as code with burn-rate alerts; this file is the human-readable register that code is checked against. **Status today: defined, not instrumented.** Instrumentation lands with the production account by Fri Dec 11, 2026 (gate M4, [`compliance/README.md`](compliance/README.md) row M4-02).

## Rules (ADR-093)

1. Every alert definition references an SLO from this file, or is ticket-only. An alert with neither is rejected.
2. **Paging** happens only on burn of a customer-impacting target. Everything else becomes a ticket. With one person on call (ADR-100), a page that is not customer-impacting is a defect in the alert.
3. **Error-budget policy.** When a budget is exhausted, the next batch of merges contains reliability work only, until the budget recovers. Feature work waits. This is recorded in the batch description.
4. A target is changed only by a new ADR or a dated entry in `docs/product/decision-log.md`. Targets marked *binding* come from ADR-093 and are not loosened. Targets marked *inferred* are the plan's starting estimates and may be tightened or corrected once there is a month of data; record the change here with the date.
5. The synthetic canary firm runs the end-to-end flow every 15 minutes and is the measuring instrument for several rows below.

## Burn-rate arithmetic

For a 30-day, 99.9% objective the error budget is 0.1% of requests, or about 43 minutes of full outage. A burn rate of 1 spends exactly the budget over the window.

| Alert | Spend | Window | Burn rate | Action |
|---|---|---|---|---|
| Fast burn | 2% of the budget | 1 hour | 14.4 | Page |
| Slow burn | 5% of the budget | 6 hours | 6 | Page |
| Budget gone | 100% | 30 days | 1 | Policy rule 3 applies |

## Objectives

| ID | Indicator (SLI) | Objective | Window | Source | Alert | Runbook |
|---|---|---|---|---|---|---|
| SLO-01 | API availability: non-5xx share of authenticated `/v1/*` requests (excluding server-sent events and client errors) | 99.9% | 30 days | binding | Page on fast or slow burn | RB-01, RB-06 |
| SLO-02 | Interactive read latency, 95th percentile, GET `/v1/*` excluding previews and event streams | under 400 ms | 30 days | inferred | Ticket | RB-06 |
| SLO-03 | Upload to scanned to preview ready, 95th percentile, files up to 10 MB | under 2 minutes | 7 days | inferred | Page through canary failure | RB-24, RB-06 |
| SLO-04 | Interactive screening | 95% complete within 30 seconds | 30 days | binding | Ticket; page if the canary fails | RB-03, RB-06 |
| SLO-05 | Agent run schedule-to-start, interactive work class | 95th percentile under 10 seconds; hard ceiling 120 seconds | 7 days | inferred (ceiling is the work-class `max_wait`) | Page when the ceiling is breached for more than 5 minutes | RB-06, RB-23 |
| SLO-06 | Event delivery to the browser, outbox commit to client | 95th percentile under 5 seconds | 7 days | inferred | Ticket (polling fallback covers it) | RB-28 |
| SLO-07 | Approved follow-ups and emails handed to the mail service | 99% within 15 minutes; delivered share at least 98% | 30 days | binding (15 minutes); delivered share inferred | Page on a stalled queue | RB-20, RB-06 |
| SLO-08 | Ledger initial pull for a typical company | under 1 hour | per run | binding | Ticket | RB-04 |
| SLO-09 | Sync freshness: active closes hourly (plus or minus 15 minutes); active engagements at least daily | as stated | rolling | binding | Ticket; page if more than 20% of connections are stale | RB-04, RB-05 |
| SLO-10 | Canary end-to-end flow | at least 99% of 15-minute runs pass | 24 hours | inferred | Page after 2 consecutive failures | RB-01 |
| SLO-11 | Durability: recovery point objective | 5 minutes | n/a | binding | Verified by drills, not alerts | RB-10, RB-15 |
| SLO-12 | Durability: single data-centre failure | Recovers automatically | n/a | binding | Verified by drills | RB-10 |
| SLO-13 | Durability: regional recovery time | under 8 hours | n/a | binding | Verified by yearly tabletop | RB-11 |

SLO-11 to SLO-13 are targets proven by the quarterly restore drill and the yearly regional-failover tabletop (chapter 06 §4), not by a running alarm.

## Where each lives (to fill as it is built)

| Item | Location | State |
|---|---|---|
| SLO definitions as code | `infra/` (path set when the production account lands) | planned |
| Burn-rate alarms | Same | planned |
| Dashboard | Same | planned |
| Error-budget review record | Dated entry in the compliance tool at each review below | planned |

## Review

Review this file monthly for the first three months after the production account lands, then quarterly. At each review record: budget remaining per paging SLO, any alert that paged without customer impact, and any inferred target to confirm or tighten.
