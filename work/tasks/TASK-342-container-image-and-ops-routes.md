---
id: TASK-342
title: "Q-01-T06 and Q-01-T16 · Container image, and the P-45 operational routes and middleware"
spec: SPEC-050
acceptance_criteria: [AC-10, AC-24]
risk_zone: red
status: in-progress
epic: Q-01
plan_key: Q-01-T06, Q-01-T16
branch: worktree-agent-a64d084b1209211aa
worktree: agent-a64d084b1209211aa
created: 2026-10-21
updated: 2026-10-21
---

> **Rules for the agent working this task**
> - Solo edition: one builder, no approvals, no reviewers to wait for (`docs/plan/AMENDMENT-solo.md`).
> - Local stack only (`make worktree-env`, then the Makefile's targets). Nothing here talks to AWS or a hosted database; no `terraform plan` or `apply`.
> - The repository is public: no credentials, account IDs or real ARNs anywhere.
> - Planning files for the same rows exist from kickoff: TASK-147 (T06). This task supersedes it for the build. T16 had no task file.

## Objective

1. **T06 (AC-10).** The backend image builds, runs non-root on a read-only root filesystem, and the kernel/isolation child limits pass in a Linux container.
2. **T16 (AC-24).** Exactly the routes on the public-route list answer without a token: `GET /healthz` and `GET /readyz`. Body-size limits, `TrustedHost` and proxy headers are in `create_app()`.

## Scope

**In**
- `backend/Dockerfile`, `backend/.dockerignore`, `backend/docker-entrypoint.sh` (api, worker `--classes`, migrate, bootstrap, ops).
- `abacus/api/public_routes.py` (the list and the two handlers), `abacus/api/middleware.py`, `create_app()` wiring, settings `trusted_hosts` and `portal_base_domain`, ROUTE-001 reading the list.
- `kernel` probes `/readyz` calls: `ping_identity`, Temporal health, scanner ping, platform key probe.

**Out**
- The edge 403 for `/healthz` and `/readyz` (CloudFront, Q-01-T15) and anything needing AWS.
- `/v1/portal/branding` (P-08) and `/v1/auth/*` (P-01): they extend the list in their own tasks.
- Per-token rate limits (G16), CORS (stays off).
- ECR push, SBOM, provenance, Inspector (Q-01-T11).

## Plan

### T06 image

- One `backend/Dockerfile` with stages `builder`, `test` (opt-in target), `runtime` (the default, last).
- Base `python:3.12-slim` pinned by the multi-arch index digest (an `ARG`, refreshed by the weekly base rebuild in T11). `python` is on the allowlist for this (Q-01-T05).
- Builder installs `uv` (pinned `0.12.3`, the version the repo's CI uses; not shipped) and runs `uv sync --locked --no-dev`, dependencies before code for layer caching. Bytecode is compiled at build time because the root filesystem is read-only.
- Runtime: uid/gid 10001, no login shell, no home. `/app` is root-owned and read-only to the app user. `HOME` and `TMPDIR` are `/tmp` (a tmpfs in the task definition).
- Entrypoint `abacus-entrypoint`: `api` (uvicorn `--factory --proxy-headers`, forwarded IPs from `ABACUS_FORWARDED_ALLOW_IPS`), `worker --classes`, `migrate` (`alembic upgrade head`), `ops <tool>` (`abacus_tools.<tool>`), `bootstrap` (exits 64 until Q-01-T20 builds it).
- The `test` target adds the dev group and `tests/`; it runs the Linux-only checks inside the image's base.
- Build context is `backend/`, so `.dockerignore` lives there.

### T16 routes and middleware

- `api/public_routes.py`: `PUBLIC_ROUTES` maps path to handler. `create_app()` registers each one with `add_api_route`, GET only, out of the OpenAPI document. Nothing else registers an unauthenticated route.
- `/healthz`: liveness, no dependency calls. `/readyz`: DB app role, DB identity role, Temporal, scanner, platform key, each under a short timeout, run together. 200 `{"status": "ready"}` or 503 with the names of the failed checks only (never an error text). Logged without values.
- Middleware (`api/middleware.py`, pure ASGI so a body is refused before it is read): body limit (JSON 1 MB, uploads 50 MB = `MAX_CONTENT_BYTES`, both by `Content-Length` and by bytes counted on a chunked body), `TrustedHost` from settings `trusted_hosts` (400), proxy headers from the ALB only (uvicorn's trusted list; `X-Forwarded-Host` is a branding hint and is never read for tenant resolution).
- ROUTE-001 (`banned_patterns.py`): `PUBLIC_ROUTE_EXCEPTIONS` is the protected list; `public_routes.PUBLIC_ROUTES` must be a subset, and `app.py` may not register a path literal.
- Settings: `trusted_hosts` (default loopback names locally, required outside local), `portal_base_domain`.

Rollback for both: revert. No migration, no dependency.

## Definition of done

- [x] Image builds from a clean context; `docker run --user` shows uid 10001; a write under `/app` fails on `--read-only`; `--tmpfs /tmp` is enough to run.
- [x] `--target test` image passes the isolation-limit tests as uid 10001 on a read-only root.
- [ ] `/healthz` and `/readyz` answer; every other unlisted path is 401 or 404; ROUTE-001 covers the list.
- [ ] Body limit, TrustedHost and proxy-header behaviour proven by tests.
- [ ] `make check-fast`, `cd backend && uv run pytest tests/unit -q`, integration tests for what is touched.

## New dependencies

None. `uv` is installed only in the builder stage, at the version the repo already uses.

## Progress log

- `2026-10-21` T06 built. `docker build backend` takes about 90 s cold (614 MB). Runtime image: uid 10001, read-only root works, `bootstrap` exits 64, `migrate` reaches for the database (refused locally with no stack, as expected). Test target: 39 tests (extraction, isolation limits and scanning) pass in a Linux container as uid 10001 on a read-only root.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|
| Build context is `backend/`; `.dockerignore` sits there | The image needs nothing from the repo root; a smaller context | no |
| `uv` installed with pip in the builder, not copied from `ghcr.io/astral-sh/uv` | That image is not on the `containers` allowlist; the pip route adds no image and keeps the pin | no |
| The `test` stage is part of the Dockerfile | AC-10 asks for a Linux container test of the isolation limits; the same base and lockfile make it honest | no |
| Public routes are registered from a path-to-handler map in `create_app()`, not decorated | `app.py` is the one file that may add routes (ROUTE-001), and a map makes the list the registration | no |

## Gotchas and discoveries

- `ENTRYPOINT []` in the test stage, or pytest would be passed to the app entrypoint.

## Questions for the human

- [ ] None.

## Handoff

See the progress log.
