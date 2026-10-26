---
id: TASK-1194
title: Screening aggregate (DEC-48) — migration 0154 screening_named_checks, code-composed request-batch rows, the SHL-20 card, rerun and feedback, TRI fail-closed, withdrawn versions excluded (P-06-T20)
spec: SPEC-319
acceptance_criteria: [AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T20
branch: s8a-screening-aggregate
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The period verdict comes only from code and no aggregate path writes request status or review decisions." P-06 §3.5 (Stories 5.1 to 5.3), §4.2 (`screening_named_checks`), §4.3 (SHL-20 rows), §4.5 (the composing subscribers); DEC-48, DEC-221; withdrawn versions left out (DEC-298, DEC-299); agents propose, people decide (ADR-005).

## Plan (red zone)
- **Migration `0154_screening_named_checks.py`** (down_revision 0146), exactly §4.2:
  - `screening_results` + `subject_kind` (`version` default, `request_batch`); the five per-run columns drop NOT NULL under two shape CHECKs; `screening_results_once_per_run` becomes a partial unique index on `version` rows; `created_by_kind` CHECK pairs `version`/`agent` and `request_batch`/`system`.
  - Aggregate columns, required by CHECK on `request_batch` rows and NULL on `version` rows: `request_item_id` (FK `request_items`), `batch_no` (partial unique per item), `source_result_ids`, `source_review_ids` (the upload reviews composed: see DEC-324), `evidence_version_ids`, `checks`, `file_flags`, `verdict`, and `supersedes_id` (FK to the table, unique).
  - Insert-only stays. A BEFORE INSERT guard on `request_batch` rows requires the `system` actor (an agent or a person never writes one), `batch_no = max + 1` and `supersedes_id` = the item's previous head.
  - A new BEFORE INSERT trigger on `review_decisions` lets `screening_result_id` name only `version` rows (§4.2 (7); a separate trigger rather than a fourth copy of 0132's function body, DEC-324).
  - `insert_columns` lists the new columns. **New** `screening_feedback` (forced RLS, insert-only, human-only guard, `CHECK (thumb = 'up' OR reason_code IS NOT NULL)`, the result must be a `request_batch` row of the same engagement).
  - Downgrade refuses while any `request_batch` row exists.
- **Composer** `agents/screening_aggregate.py`:
  - Pure `compose(...)` over code facts (upload checks, document dates, the request's period) and verified review flags. The period check reads code only.
  - `compose_for_item(tenant_id, item_id)` runs in a system context. It reads the live fulfilments (`requests.api.read_item_versions`) minus `evidence.api.withdrawn_among`, inserts a superseding row only when the composition changed, and audits `screening.completed`.
- **Subscribers:** `upload_checks.recorded` (beside the reviewer start), the new `upload_review.recorded` (emitted in the reviewer's unit of work), and `evidence_version.withdrawn` recompose every item the version fulfils.
- **Routes** in `agents/screening_contract.py` go live behind `screening.card`:
  - `GET …/screening` (`upload_review.read`);
  - `POST …/screening/rerun` (`screening.request`; 202; 409 `screening_running`; reviews only versions without a completed review under the current prompt);
  - `POST /v1/screenings/{id}/feedback` (`screening.feedback`, 201).
  - The screening-return draft stays 501 (P-06-T22).
- **TRI fail-closed:** on a `tax_return` work item at a firm that is not synthetic (C19's §7216 consent registration is not built, so none exists), `create_review_run` makes no run and no model call, and the aggregate's model check stays `not_run`. Code checks still run.
- **Existing reads:** the per-version reads of `screening_results` (`latest_results`, `latest_result_for_version`, `result_for_run`, `screening_results_of_run`) add `subject_kind = 'version'`. Without it, `_shown_run`'s `NOT IN` passes a NULL run id whenever no shadow run exists, so an aggregate would reach the board. The stage tool and eval runner join on the run and need nothing.
- **Registry:**
  - agents `TABLES`/`INSERT_ONLY`/`INSERT_COLUMNS` (`screening_feedback`, new `screening_results` columns);
  - `schema_check` pins (the guard functions are SECURITY INVOKER: no DEFINER registration);
  - the worker subscription pin (`upload_review.recorded`).
- **Tests first:**
  - `tests/unit/agents/test_screening_aggregate.py` (the rule, property-tested; the period never reads the model; withdrawn left out);
  - `tests/integration/backfill/test_p06t20_screening_aggregate.py` (AC-21 to AC-28 over HTTP and the migrated database);
  - the C5 SHL-20 contract test moves the three routes from stubbed to live.
- **Rollback:** `alembic downgrade 0146` (refuses once aggregates exist; then revert the code and leave the rows). Turning `screening.card` off hides every route.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built. Tests:
  - `tests/unit/agents/test_screening_aggregate.py`: 14 tests, two of them property-based;
  - `tests/integration/backfill/test_p06t20_screening_aggregate.py`: 14 tests, AC-21 to AC-28;
  - `test_schema_check_db`: the pinned insert columns.
  - The C5 SHL-20 contract test moves the card, rerun and feedback to live. The screening contract and worker pins gain `upload_review.recorded` and `evidence_version.withdrawn`.
  - `make regenerate`: OpenAPI drops 501 from the three routes; the tenant-isolation table list gains `screening_feedback`.
  - Error code `screening_running` written.
- 2026-10-26: the AC-21 and AC-28 database rules are tested independently in `backfill/test_p06t23_withdrawal_race_and_screening_rows.py` (TASK-1280).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-324 | The aggregate as built: inputs, the period rule, what counts as screened, the review-decision guard, TRI fail-closed | No |
- 2026-10-25: the agents schema suite (`test_ac14_the_app_cannot_set_who_created_a_screening_result`) caught the app's insert grant gaining `created_by_kind`. The grant is reverted: the insert guard now sets `system` on aggregates, and `created_by_kind` stays the database's (SPEC-011 AC-14). Runs:
  - the full `tests/unit tests/contracts tests/security`: 28,488 passed, 5 xfailed;
  - the screening, agents, upload-review, withdrawal, citations, schema-check and worker files: 595 tests; the one failure is fixed, and its 80 re-run tests pass.
- 2026-10-25: security review fixes (DEC-324), each with a test that failed first:
  - rerun starts reviews only with `upload_review.request` and `upload_review.enabled`;
  - deterministic `uuid5` source events, an advisory lock per item, and a 60-s per-item rate limit (`screening_rerun_requests`, 0154); parallel reruns start exactly one run;
  - the gateway boundary refuses `tax_return_information` for every agent (`test_gateway_tax_return.py`: screener, matcher, reviewer);
  - the 0154 trigger functions pin `search_path`;
  - the app writes `version` rows only as the agent.
