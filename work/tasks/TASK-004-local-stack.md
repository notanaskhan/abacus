---
id: TASK-004
title: Local development stack with Postgres, write-once storage and Temporal
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-progress
branch: spec-000-planning
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Give every later SPEC-000 task the services it needs — PostgreSQL with pgvector, S3-compatible storage with Object Lock, and a Temporal dev server — through `docker compose` for `make dev`, and the same images through testcontainers for integration tests, with every image pinned by digest and approved like any other dependency.

## Scope
**In**
- `docker-compose.yml` at the repo root with services `db`, `minio`, `temporal` (the names `make dev` already uses); healthchecks; named volumes; ports bound to `127.0.0.1` only; local-only credentials that are obviously not secrets
- Image references pinned by digest, in `docker-compose.yml` only (one source of truth)
- A `containers:` section in the dependency allowlist, and `check_dependencies` extended to fail on an image that is unlisted, pending, or not pinned by digest
- `backend/tests/integration/conftest.py`: session-scoped testcontainers fixtures that read image references from `docker-compose.yml`
- Integration smoke tests: Postgres accepts connections and `CREATE EXTENSION vector` works; MinIO creates a bucket with Object Lock and refuses to delete a locked object version; Temporal's frontend reports healthy
- CI: integration tests run in stage 2 (GitHub runners have Docker)

**Out**
- Database roles, row-level security, migrations (TASK-005)
- Buckets, retention policies, keys (TASK-009)
- Temporal namespaces, workers, workflows (TASK-010)
- The fake OpenID Connect provider container (TASK-007)
- Making `make dev` start the API and worker (they don't exist until TASK-008/010)

## Context to load
- ADR-014 (Postgres), ADR-016 (S3 Object Lock), ADR-017 (Temporal), ADR-077 (integration tests via containers), ADR-087 (local environment)
- `Makefile` (`dev`), `docs/architecture/dependency-allowlist.yaml`, `backend/src/abacus_tools/quality/check_dependencies.py`

## Plan
- [x] Plan approved by human (founder, 2026-10-06: "proceed with your recommendations")
- [x] Approval file `work/approvals/TASK-004.yaml` written by the agent at the founder's instruction (2026-10-06)
- Approved by founder: paths under *Approval file text*, expires 2026-10-20
- [x] Q1–Q3 answered: all recommendations approved (2026-10-06)

Steps:
1. [x] **Images (Q1).** Resolve current digests for `pgvector/pgvector:pg17`, `minio/minio` (latest release tag), `temporalio/temporal` (CLI image; runs `server start-dev`), and add them to the allowlist's new `containers:` section with reasons.
2. [x] **`docker-compose.yml`.** Three services, `image: <name>:<tag>@sha256:<digest>`, healthchecks (`pg_isready`; MinIO `/minio/health/ready`; `temporal operator cluster health`), named volumes, `127.0.0.1` port bindings (5432, 9000/9001, 7233/8233). Credentials are fixed local values (`postgres`/`postgres`, `minioadmin`/`minioadmin`) — accepted by `secrets_scan` by design (no digits) and unusable outside localhost.
3. [x] **`check_dependencies` (Q2).** Parse `docker-compose.yml` (and any `compose*.y*ml`); each `image:` must be `name:tag@sha256:<64 hex>` and approved under `containers:`; messages follow the existing format. Interface contract below; tests from the independent author.
4. [x] **testcontainers fixtures** in `backend/tests/integration/conftest.py` reading images from `docker-compose.yml`; containers started once per session, torn down after.
5. [x] **Smoke tests** `backend/tests/integration/test_local_stack.py` (`test_ac20_*`): Postgres + `vector`; MinIO Object Lock bucket refuses a governance-mode delete; Temporal healthy.
6. [x] **Verify:** `docker compose up -d db minio temporal` healthy locally; `make check` passes locally and in CI; gate-break: an unpinned image and an unlisted image each fail `check_dependencies`.

Files to create or change:
- `docker-compose.yml` *(new; protected by Q3)*
- `docs/architecture/dependency-allowlist.yaml`, `backend/src/abacus_tools/quality/check_dependencies.py`, `backend/tests/unit/quality/test_check_dependencies.py` *(protected)*
- `backend/pyproject.toml`, `backend/uv.lock` *(protected — `testcontainers`, already approved, joins the dev group; `boto3` and `asyncpg`, already approved runtime, for the smoke tests)*
- `backend/tests/integration/conftest.py`, `backend/tests/integration/test_local_stack.py`
- `.claude/hooks/_protected.py`, `.github/CODEOWNERS`, `docs/architecture/protected-paths.md` *(protected; only if Q3 = yes)*

### Interface contract for `check_dependencies` (tests written independently — ADR-078)
- Reads every `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, `compose.yaml` under the repo (same directory exclusions as `package.json`).
- For each service `image:` value: must match `<name>[:<tag>]@sha256:<64 lowercase hex>`; the `<name>` (without tag/digest) must be `approved` under `containers:` in the allowlist (glob keys allowed, exact keys win).
- New messages: `<rel>: <image> must be pinned by digest (name:tag@sha256:...)`; `<rel>: <name> is not in the dependency allowlist`; `<rel>: <name> is pending in the dependency allowlist, not approved`.
- A service with `build:` and no `image:` is refused: `<rel>: service <service> builds an image; build steps are not allowed in compose files`.

### Approval file text
```yaml
task: TASK-004
approved_by: founder
expires: 2026-10-20
paths:
  - docs/architecture/dependency-allowlist.yaml
  - backend/src/abacus_tools/quality/check_dependencies.py
  - backend/tests/unit/quality/test_check_dependencies.py
  - backend/pyproject.toml
  - backend/uv.lock
  - .claude/hooks/_protected.py
  - .github/CODEOWNERS
  - docs/architecture/protected-paths.md
  - docker-compose.yml
reason: TASK-004 — local stack, container images in the allowlist
```

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass — including pinned, approved images
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation — n/a
- [ ] AI calls (if any) go through the gateway — n/a
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed
- [ ] Both CI jobs pass on the PR

Commands:
```
docker compose up -d db minio temporal
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| testcontainers (py dev) | pinned in `uv.lock` | Integration tests start the same images (ADR-077) | Allowlist (approved) |
| asyncpg, boto3 (py runtime) | pinned in `uv.lock` | Smoke tests now; product code later | Allowlist (approved) |
| `pgvector/pgvector`, `minio/minio`, `temporalio/temporal` (container images) | pinned by digest | Local and test services | Founder, 2026-10-06 (Q1) |

## Progress log
- `2026-10-06` — Founder approved the SPEC-000 breakdown and recommendations (fake OIDC provider for the skeleton; staging last; agent-drafted designs for red tasks, line-by-line review). Docker Desktop started (28.4.0). Plan written; awaiting approval. No code.

- `2026-10-06` — Implemented. Compose files protected first (hook, CODEOWNERS, protected-paths.md; hook verified: approved `docker-compose.yml` allowed, others and unapproved blocked).
  - **MinIO's community image is no longer published** (Docker Hub repo gone; quay.io requires login). Probed Versity Gateway v1.8.0: Object Lock enforced (locked version delete → AccessDenied; governance bypass works). Founder approved Versity instead (2026-10-06); compose service renamed `minio` → `s3` (Makefile `dev` updated).
  - Founder also approved: DB-001 excluded for `tests/integration/*` (container smoke tests need raw connections); `types-boto3[s3]` and `asyncpg-stubs` (allowlisted) instead of the test author's file-level pyright switch-off. Approval file extended with `Makefile`, `banned_patterns.py`, `test_banned_patterns.py` at the founder's instruction.
  - Local adjustments: Postgres on host port 55432 (5432 taken by a local Postgres); Temporal dev server in memory (it runs non-root and can't write a root-owned volume).
  - Lint exemptions for `tests/integration/**`: S105/S106 (fixed local container credentials), S310 (HTTP health checks to local containers) — scoped in `pyproject.toml`, no inline suppressions.
  - Independent tests (Sonnet, from the contract): 87 image cases in `test_check_dependencies.py`, 16 integration tests. One bug in their test (expected list not sorted) returned to them and fixed by them. One reasoned `pyright: ignore` remains on `boto3.client("s3", …)` (overloads span every AWS service).
  - My mistake: during gate-break cleanup a `git checkout` of the allowlist discarded its uncommitted edits; re-applied and re-verified.
  - Gate-break: unpinned image and pending image each fail `check_dependencies`. `make check` exit 0 (integration 16 passed against live containers).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Image references live only in `docker-compose.yml`; tests read them from there | One source of truth for local and test services | no |
| testcontainers for tests, compose for `make dev` | Tests stay self-contained in CI and locally (ADR-077) | no |
| Ports bound to `127.0.0.1` | Local services never exposed on the network | no |
| Versity Gateway instead of MinIO | MinIO's community image is no longer public; Versity enforces Object Lock (probed) | no |
| Temporal dev server in memory locally | Non-root image can't write a root-owned volume; local history loss is acceptable | no |

## Gotchas and discoveries
- `make dev` also starts `abacus.api.main` and `abacus.worker.main`, which don't exist until TASK-008/010; until then use `docker compose up -d db minio temporal`.

## Questions for the human
- [x] **Q1 — Container images.** Approved 2026-10-06. Approve `pgvector/pgvector` (Postgres 17 with pgvector, ADR-014), `minio/minio` (S3-compatible with Object Lock, local only; ADR-016, ADR-087) and `temporalio/temporal` (Temporal CLI dev server, local only; ADR-017). **Recommendation:** approve all three, pinned by digest.
- [x] **Q2 — Images in the allowlist.** Approved 2026-10-06. Add a `containers:` section and have `check_dependencies` refuse unpinned or unlisted images. **Recommendation:** yes — images are dependencies with the same supply-chain risk.
- [x] **Q3 — Protect `docker-compose.yml`.** Approved 2026-10-06. **Recommendation:** yes — it decides which images run with local data and which ports open.

## Handoff
- **Current state:** Steps 1–6 done; `make check` exit 0 locally. PR open on `spec-000-planning`.
- **Exact next step:** Confirm CI (integration tests need Docker on the runner), cross-model review, founder merges; then TASK-005 plan.
- **Uncommitted or partial work:** none.
- **Known failing checks:** none.
- **Open issues:** PR #3 security should-fixes (handled in a separate worktree); branch protection off.
