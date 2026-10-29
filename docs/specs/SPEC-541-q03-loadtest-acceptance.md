---
id: SPEC-541
title: Load-test harness acceptance (Q-03-T114, catch-up lane 2027 Q2 part 2)
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: []
related_specs: []
created: 2026-10-29
updated: 2026-10-29
---

> **Instructions for coding agents**
> - This spec carries Q-03-T114's acceptance for the load-test harness built by Q-03-T035
>   (TASK-1288) and Q-03-T043 (TASK-1362). Q-03 has no epic SPEC; the source is
>   `docs/plan/epics/Q-03.md` E1/E2, the backlog rows and `docs/ops/loadtests/README.md`.

## 1. Summary
Acceptance tests, written from the plan rows and the runbook, that prove the load-test harness
reports per endpoint group, never runs beside a hosted build or deploy, and feeds the x1 smoke's
trend to the quality report.

## 2. Problem and context
The harness's own tests were written in the session that built it. The catch-up lane asks for an
AC suite written from the spec only. Under the solo amendment (ADR-078's split is void) the same
builder writes it, test first; a gap the suite finds is fixed in the same task.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| The builder | Runs `make loadtest` locally and the x1 smoke after a staging batch deploy |

## 5. Acceptance criteria
- **AC-1** `make loadtest PROFILE=smoke` plays a committed profile and writes p50/p95/p99 per
  endpoint group (nearest-rank, client side) as JSON and Markdown; every committed profile loads
  by name and an unknown field or name is refused.
- **AC-2** A run (not a dry run) refuses before any request while the deploy lock of
  `ABACUS_DEPLOY_LOCK_ENV` is held, naming the holder, and while any database setting points at a
  hosted database, naming the setting and never its value. A dry run still prints the plan.
- **AC-3** The x1 smoke's own reports feed `abacus_tools.loadtest.trend`, which posts the trend to
  the quality report's Ops row and, past +20% over the 4-week median, writes a ticket of results
  only and exits 1.

## 6. Open questions
- None.
