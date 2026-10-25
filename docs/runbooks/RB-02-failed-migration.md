---
id: RB-02
title: Failed migration
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2026-11-13
---
# RB-02 · Failed migration

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 to SEV1 |
| Linked from | none yet (the deploy run's Migrate step goes red) |
| SLO affected | none while the old code serves; SLO-01 if it does not |
| Kill switches that apply | read-only mode (Q-01-T37) if a half-applied change corrupts writes |
| Rehearse by | R0 (Fri Nov 13, 2026) |
| Last rehearsed | never |
| Last reviewed against an incident | never |

The deploy's Migrate step runs `alembic upgrade head` as `abacus_owner` with `lock_timeout=5s`, before any service changes (Q-01-T18). If it fails, the deploy stops there and the old code keeps serving against whatever the migration left. Migrations are single and reversible before the first real firm, and never downgraded on a hosted database (P-38, ADR-117).

## 1. Recognise it
- The deploy run is red at **Migrate**, with `::error title=<migrate task definition> failed::exit code <n>`.
- The migrate task's log (CloudWatch, the migrate task's log group, the run's task id) ends in an Alembic or Postgres error. `canceling statement due to lock timeout` means another session held a lock for more than 5 seconds.

## 2. Contain
Nothing to roll back: the services were not touched. Confirm the old code serves (`/readyz` through the load balancer, the canary's next run). Do not start a second deploy until step 4 is answered. The deploy released its lock; `make deploy-lock ENV=<env>` should say `free`.

Never run `alembic downgrade` against staging or production (the shell hook refuses it), and never open a database console to "fix it by hand": that needs break-glass (RB-12) and a recorded reason.

## 3. Preserve
The migrate task's full log, the revision it was applying, and `alembic current` from an ops task:

```
gh workflow run ops-task.yml   # staging only; production through an ops request
```

(There is no `alembic current` ops command yet: read it from the migrate log's first lines, which print the starting revision.)

## 4. Assess
- **Lock timeout:** nothing changed (the transaction rolled back). Cause: a long transaction or a busy table. Re-dispatch the deploy in a quiet window.
- **Error inside the migration, transactional DDL:** Postgres rolled the whole migration back. The schema is at the previous head. Fix the migration on a branch.
- **Error after a non-transactional step** (`CREATE INDEX CONCURRENTLY`, an `autocommit_block`): the schema is part-way. Read which statements ran. This is SEV2 at least; if the old code fails against it, SEV1 and RB-01.

## 5. Notify
Staging: none. Production: a status-page note only if customers see errors (they should not while the old code serves).

## 6. Recover
1. Fix forward with a new revision on a branch (a migration on `main` is never edited, AGENTS.md rule 14). Keep it expand-only within the release.
2. For a part-applied non-transactional step, the new revision makes the step idempotent (`IF NOT EXISTS`, `DROP INDEX CONCURRENTLY IF EXISTS` then create).
3. Merge in the next window; dispatch the deploy again. The migrate step applies the new revision.

## 7. Verify
The deploy's Migrate step is green, `alembic heads` printed in pre-flight equals the migrate log's final revision, and the services roll and the smoke passes.

## 8. Review
Typical actions: a schema-check expectation, a migration test in `tests/integration`, or a lint for the statement that failed.

## Rehearsal log
| Date | Kind (drill, staging walk-through, tabletop) | Result | Changes made |
|---|---|---|---|
