---
id: TASK-8868
title: "S52: Rebalance the unit and integration CI shards"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: shard-rebalance
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-21
updated: 2026-11-21
plan_key: S52
---

## Objective
Every recent main run cancelled integration shards at the 100-minute timeout and unit shard 2 at 45 minutes with no failures (b86661661, run 44879204831). Make every shard finish, without skipping tests or raising timeouts.

## Done
- Cause: tests/durations.json (last recorded S49) knew 89 of 748 integration files; the rest weighed as the median file, so shard 3 drew 14,147 tests (13,140 in the generated permission matrix) and eight shards ran past 100 minutes
- abacus_tools.ci.shard --by-count: an unrecorded file weighs its collected test count times the recorded seconds per test (collect-only pytest session in process); the Makefile's ci-unit and ci-integration pass it
- durations.json regenerated empty (--record of an empty report): its S49 times were stale and the counts take over until runs refill it
- Recorder: with ABACUS_DURATIONS_OUT set, tests/conftest.py appends each test phase's seconds as a JSON line as the run goes (controller only under xdist); CI uploads it per shard with if: always(), so a cancelled shard still records
- shard --record-runs [--partial] merges those files into durations.json (a partial run only raises a time; deleted files drop out)
- Shards: integration 10 to 20 (about 625 tests each; the matrix, route introspection and tenant isolation files alone), unit 2 to 3 (about 20k to 24k tests each)
- Tried: a full local recording; abandoned after each of the 3 workers spent 2.9 hours in session setup on this laptop's Docker (8 GB, shared), so the first real timings come from the tip CI run's artifacts

## Progress log
- `2026-11-21` — Built and checked locally: shard tests 19 pass, every file in exactly one shard for 20 integration and 3 unit shards, ruff, pyright, banned_patterns. After the tip CI run: download durations-* artifacts and run shard --record-runs (then --partial if any shard was cut) in the next batch. DEC-5865.
