---
id: TASK-1202
title: Pen-test self-assessment fixes - the database client verifies TLS certificates (G-09), the letter-policy body forbids extra fields (ED-034, G-18)
spec: SPEC-050
acceptance_criteria: [AC-17]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T017 follow-up (S8 wave A, A7)
branch: s8a-identity-security
created: 2026-10-25
updated: 2026-10-25
---

## Objective
SPEC-050 AC-17's settings validation outside local and test gains the database TLS rule. G-09: "The database client does not require certificate verification, and settings do not refuse a DSN without it." ED-034: "`PUT /v1/firm/letter-policy` accepts undeclared fields."

## Plan (red zone: kernel db)
- **Code:** new `kernel/db_tls.py` (outside `kernel/db` so `kernel.config` can use it without an import cycle): `database_tls(url, local, ca_file)` answers the driver URL (the DSN's `ssl`/`sslmode` removed) and either `False` (plain: local stack only, when nothing asks for TLS or the DSN turns it off) or a `verify-full` context (`CERT_REQUIRED`, host name checked, TLS 1.2+, the configured CA bundle or the system store). Any requested TLS mode (`prefer`, `require`, `verify-ca`, ...) is upgraded to `verify-full`; outside local and test TLS is always on. `kernel/db/session._create_engine` (app, relay, identity engines) and `migrations/env.py` pass it as asyncpg's `ssl`.
- **Settings:** `database_ca_file` (Internal); a validator refuses a database DSN with TLS off outside local and test.
- **ED-034:** `LetterPolicyIn` (`extra="forbid"`) as the route's body; the strict xfail in `tests/unit/api/test_request_bodies.py` removed (the check finds no other body); `make regenerate`.
- **Tests:** `tests/unit/kernel/test_db_tls.py`, two cases in `tests/unit/kernel/test_config.py`, `tests/integration/test_db_tls.py` (a local plain connection works; a DSN asking for TLS against the compose Postgres, which serves none, fails instead of falling back).
- **Rollback:** revert the commit; no migration.

## Progress log
- 2026-10-25: built. Unit: `test_db_tls.py` 14, `test_config.py` +12, `test_request_bodies.py` 209 (no xfail). Integration: `test_db_tls.py` 2, `test_uow_session_rollback.py`, `test_migrations_env.py`.
- **Human to-do before the next hosted deploy:** set `ABACUS_DATABASE_CA_FILE` to the RDS CA bundle baked into the image (the system store does not hold Amazon's RDS roots), or the API, worker and migration job will refuse the database's certificate. The `abacus_tools` operator commands (`tenants.py`, `signup_codes.py`, `access_review.py`) still call `asyncpg.connect` without a context: a follow-up should give them the same `database_tls` call.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| A requested weaker TLS mode is upgraded to `verify-full`, never honoured | "Whenever TLS is in use, verify" (G-09) | No |
| Local and test default to an explicit plain connection, not asyncpg's `prefer` | `prefer` is opportunistic TLS with no verification | No |
| DEC-332 | Recorded in the decision log with the human to-do | No |
