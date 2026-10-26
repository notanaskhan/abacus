---
id: TASK-1287
title: "Agent run records (P-47, conflict C-12): insert-only agent_run_records persisted at completion by the specialists through patched workflows"
spec: SPEC-341
acceptance_criteria: [AC-44]
risk_zone: red
status: in-review
epic: Q-02
plan_key: Q-02-T41
branch: s9b-run-records-loadtest
created: 2026-10-26
updated: 2026-10-26
---

## Objective
ADR-169 §3 (accepted): one durable, insert-only, content-free record per completed specialist
run, written once at completion by a `persist_run_record` activity in the run's own workflow,
kept for the engagement's retention, and readable after the raw trace (gateway attempts, model
text) is gone. SPEC-341 AC-44 is "Not built".

## Overlap with TASK-5000 (notanaskhan's C6 v1)
TASK-5000 shipped `run_record_sha256` on `GET /v1/agent-runs/{id}` (`runs.run_record_sha256`:
a read-time SHA-256 of the live `agent_runs` row) and `/trace/records-read` (sources and counts
from the run row). Both stay exactly as shipped: same names, same meaning, same routes. The
durable record's own fingerprint is `record_sha256` (ADR-169 §3), a different thing (the hash of
the stored record's fields, fixed once written). The plan row's "record_sha256" therefore names
the new column, never a rename of the run view's field. DEC-396 records the conflict (C-12).
Adding `record_sha256` / `record_persisted_at` to the run summary (ADR-169 §4) stays with C6 v1
(Q-02-T45 / P-09); this task adds only the `/record` read that ADR-169 §4 names.

## Plan
- **Migration 0171** (`0171_agent_run_records.py`, `down_revision = "0160"`; the main session
  re-points it at merge): `agent_run_records`, `run_id` primary key (with `tenant_id`) referencing
  `agent_runs`; ADR-169 §3's fields: `engagement_id` NULL (firm-level template runs),
  `work_item_id` NULL, `capability`, `spec_version`, `stage` (`shadow`|`live`), `prompt_ref`,
  `prompt_sha256`, `model`, `route`, `region`, `terms_version`, `boundary_basis`,
  `input_hashes` jsonb, `records_read` jsonb, `citations` jsonb, `outcome` jsonb,
  `initiator_user_id`, `started_at`, `completed_at`, `record_sha256` (hex), `persisted_at`.
  Forced RLS (`tenant_table`), `insert_only`, `insert_columns`, TRUNCATE revoked. A guard trigger
  requires the `system` actor and a run that has ended. Downgrade refuses while rows exist.
  No change to the human-only actions register.
- **Registry**: `agent_run_records` in agents `TABLES`, `INSERT_ONLY` and `INSERT_COLUMNS`.
- **Model**: `AgentRunRecord` in `agents/models.py`.
- **Service** (`agents/run_records.py`, new): `build_record` (pure: canonical fields and
  `record_sha256`), `persist_run_record(tenant_id, run_id)` (system context; reads the run, its
  gateway usage rows, its outputs' citations; no-op while running or once persisted; writes the
  row and `agent_run_record.persisted` (target `agent_run`, `Ref(record_sha256)`) in one unit of
  work), `record_for(ctx, run_id)` (authorised `agent_run.read` through `runs._run`; metadata
  projection drops record identifiers, DEC-87).
- **Gateway read** (`ai_gateway/attempts.py`): `model_calls_for` returns the run's calls with
  model, route, prompt, inputs hash, basis and terms version (the record's source; the trace's
  `attempts_for` is unchanged).
- **Activity** `agents.persist_run_record` (RunInput); repeat-safe.
- **Workflows** (`agents/workflows.py`): screening, upload_review, inbox_match, guidance_draft
  and entry_assess persist the record after the terminal state is written, on every path
  (success, failure, cancellation), behind `workflow.patched("run_record_v1")`. A failed persist
  never changes the run's outcome.
- **Histories**: new versions recorded by the recorders (never hand-written): screening v3,
  upload-review v2, inbox-match v2, guidance-draft v3, entry-assess v2; every older version must
  keep replaying. A stub recorder for the screening v3 completed/skipped cases.
- **Route** (contract first): `GET /v1/agent-runs/{run_id}/record` on `agent_run.read`
  (ADR-169 §4), 404 until persisted; contract doc §2/§3/§7/§8; route introspection list;
  `make generate`.
- **Tests first**: `tests/unit/agents/test_run_records.py` (canonical hash, citation scrub,
  outcome), `tests/integration/agent_tests/test_run_records.py` (AC-44: screen a run, persist,
  prune the trace, 90 days later read the record equal to the run's facts; insert-only; repeat
  safety; route; walls 404), the five replay tests listing the new histories.
- **Rollback**: revert the branch before merge. After merge: the workflows keep the patch (a
  reverted workflow would not replay histories with the marker), so a rollback removes the route
  and leaves the activity as a no-op; the table stays (downgrade refuses with rows).

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built. Tests first (`unit/agents/test_run_records.py`,
  `integration/agent_tests/test_run_records.py`, `workflows/test_run_record_replay.py`), then
  migration 0171, `run_records.py`, `ai_gateway.model_calls_for`, the activity and the
  `run_record_v1` patch in screening, upload_review, inbox_match, guidance_draft and entry_assess.
  Histories recorded with the new `abacus_tools.workflows.record_run_records` (stub activities
  on a throwaway Temporal container only): screening v3, upload-review v2, inbox-match v2,
  guidance-draft v3, entry-assess v2, each `completed` and `failed`; every older history still
  replays. The record route went contract first (`docs/contracts/agent-runs.md`, then
  `make generate`). DEC-396 records the C-12 conflict with TASK-5000 and the build choices.
- 2026-10-26: existing tests that list the screening workflow's exact activity sequence (and the
  activity count in `test_screening_contract.py`) now include `agents.persist_run_record`: the
  sequence changed by design (ADR-169), nothing was loosened. The completion test also checks
  the real workflow wrote the record.
- Not verified here: the dev database (at 0102) was not migrated; no Playwright run.

## Definition of done
- [x] AC-44 integration tests pass (7); unit tests pass (11).
- [x] Replay tests pass for every patched workflow, old and new histories (139 in the touched
  replay files).
- [x] Backend gates, schema check (192), check-heads, check-generated, web tsc.

- 2026-10-26: security review fixes (DEC-396 notes). M1: quote and sheet fingerprints are
  HMAC-SHA-256 under a per-firm key (`run_record_fingerprint_pepper`, the TIN fingerprint's
  pattern), renamed `quote_fingerprint`/`sheet_fingerprint`, `confidential`, withheld from
  readers who may not read unmasked content; no record without the pepper outside local and
  test. L1: withdrawn versions leave the read (`withheld`). L2: the guard ties stage, times and
  outcome to the run. L3: `agent_run_records` is a retention record class. Tests: run records
  14 integration, 13 unit; workflow suites 59; replay, route, schema check, isolation green.
