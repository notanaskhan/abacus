# Season setup v1 (SS-1) — manifest, cohorts, approval and execution

| Field | Value |
|---|---|
| Owner | engagements (T-08; SPEC-710) |
| Status | stub (T-08-T04, 2026-11-18; DEC-5603); v1 S52 |
| Code | `backend/src/abacus/modules/engagements/season_contract.py` (`season_router`) |
| Flag | `engagements.season_setup` (default off; off: 404; on: 501 until T-08-T09/T12) |
| Consumer tests | `backend/tests/contracts/t08_practice/` and `apps/web/src/fixtures/contracts/t08-practice.contract.test.ts` (T-08-T08) |

Names and contacts are `confidential`; no field is TRI (the planner declares no `tri`). Client 404 → flag 404 → human-only 403 → 501. Tallies and counts come from the manifest and the step log (ADR-050).

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/seasons` · `GET /v1/seasons/{tax_year}/manifests/{mid}` | `season.read` | tallies, office footings, cohorts, asks; walls on rows and counts |
| `POST /v1/seasons/{tax_year}/manifests` | `season_setup.prepare` | code build then the planner step when allowed; 409 `cohort_approved` on a rebuild over an approval |
| `GET /v1/season-cohorts/{cid}/rows?exceptions_only=&office_id=&q=` | `season.read` | rows with derived display and step log |
| `PATCH /v1/season-manifest-rows/{rid}` · `POST /v1/season-cohorts/{cid}/rows:exclude` | `season_setup.prepare` | reassign (If-Match) · exclude with a reason; 409 `cohort_approved` |
| `POST /v1/season-asks/{aid}/answer` | `season_setup.prepare` | a person's answer (`answered_by`) |
| `POST /v1/season-cohorts/{cid}/approve` · `POST …/withdraw-approval` | `season_setup.approve_cohort` | `rows_hash` + manifest version; single-use grant (ADR-161); 409 `manifest_superseded`, `execution_started` |
| `GET /v1/seasons/{tax_year}/manifests/{mid}/export.xlsx` | `export.create` | byte-stable, formula-escaped, fresh MFA |

**Slots (T-08-T09):** `engagements.api.register_season_candidate_source(kind, provider)` and `register_season_row_executor(kind, executor)` fail closed on an unknown kind. **Steps:** engagement → returns → assignments → binder → letter → consents → invitations, idempotent on (row, step).

**Examples (foot):** 214 = 65 + 30 + 42 + 19 + 38 + 20; 224 = 68 + 30 + 45 + 19 + 42 + 20; 241 = 74 + 33 + 48 + 21 + 45 + 20; created 126 = 65 + 30 + 31.
