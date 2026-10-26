---
id: TASK-919
title: Access events - partitioned insert-only table, kernel.access writer, first emitters (Q-02-T20)
spec: SPEC-319
acceptance_criteria: [AC-6]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T20
branch: q02-t20-access-events
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Downloading an evidence version or building a model context writes one identifier-only row per subject, and tenant B never reads tenant A's rows" (Q-02-T20; Q-02 AC-23, AC-25). The spec field cites SPEC-319 because Q-02's compliance-kernel spec isn't written yet; the ACs are Q-02 §3's.

## Plan
- Migration `0105_access_events`:
  - `access_events` is partitioned by month on `occurred_at`, with tenant RLS forced on the parent and on every partition;
  - an insert-only trigger (cloned to each partition) and a TRUNCATE trigger on each partition;
  - the app inserts through the parent only and holds nothing on any partition;
  - a DEFAULT partition;
  - the `access_events_partition(month)` definer, called for October 2026 to March 2027.
- `kernel.access` (the writer is in `kernel.uow.access`, which owns tenant-connection transactions):
  - `record_reads` writes one statement, committed on its own; it runs before content is served, so a failed write refuses the read;
  - `register_access_kind` registers a kind with its flags;
  - `ensure_partitions` creates partitions ahead of time.
- Emitters:
  - evidence download, version and upload page renditions, and inbox page renditions (`evidence_content.read`);
  - the gateway, which records `model_context.built` once per call for each source in `AssembledContext.sources`, just before the provider call. The upload reviewer names its version.
- schema_check: a partition is checked as a partition. Its parent must be owned; RLS must be forced, under the tenant policy; and the app must hold no privileges on it. The TABLE_OWNERS expectations leave partitions out.
- Rollback: downgrade 0105, and revert the emitters with it.

## What changed
- As planned. Tests:
  - `test_access_events.py` (6): rows, refusal, isolation, insert-only, partitions and the default partition, context sources;
  - schema_check, including the migrated partitions and a naked partition reported;
  - the evidence suites (132), with the emitters on;
  - the full `schema_check` (up, down, up).
- Also: `test_binder_lifecycle.py`'s idempotency constant is renamed so the secrets scan stops flagging it on main.

## Not done
- The monthly Temporal Schedule that calls `ensure_partitions`. No Schedule plumbing exists yet (the same gap as Q-01-T46's drain). The pre-created partitions reach March 2027, and the DEFAULT partition catches any late month.
- Other agents' context builds name no sources yet. Only the upload reviewer does.

## Progress log
- 2026-10-23: the tests above pass.
- 2026-10-26 (S10 code gap, branch `s10-q02-schedules`): `AuditPartitions` on a 30-day Schedule
  (`audit_trail/jobs.py`) runs `ensure_partitions` for this month and the next two. Tests at the
  end of the run.
