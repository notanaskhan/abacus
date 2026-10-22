# The only command surface for humans, agents and CI (ADR-010). PROTECTED.
.PHONY: setup dev seed e2e check-fast check check-generated check-heads regenerate db-guard worktree-env dev-fixtures ci-unit ci-integration ci-coverage ci-contracts ci-frontend ci-visual test test-integration evals generate migrate loadtest seed-demo seed-staging fixtures journeys journeys-full route-parity flag access-review

setup:
	cd backend && uv sync --locked
	pnpm install --frozen-lockfile
	pnpm -C packages/api-client build:types

# This checkout's local stack (F-01-T09): `make worktree-env` writes the git-ignored
# .worktree.env, giving a linked worktree its own compose project and a port offset (10, 20, …).
# Without it: project `abacus`, offset 0, today's ports. CI never has one.
-include .worktree.env
ABACUS_PORT_OFFSET ?= 0
COMPOSE_PROJECT_NAME ?= abacus
export ABACUS_PORT_OFFSET COMPOSE_PROJECT_NAME
port = $(shell echo $$(( $(1) + $(ABACUS_PORT_OFFSET) )))
export ABACUS_DB_PORT := $(call port,55432)
export ABACUS_S3_PORT := $(call port,7070)
export ABACUS_TEMPORAL_PORT := $(call port,7233)
export ABACUS_TEMPORAL_UI_PORT := $(call port,8233)
API_PORT := $(call port,8001)
# The local stack's public credentials (as in abacus.kernel.config), at this checkout's ports.
STACK_DB = 127.0.0.1:$(ABACUS_DB_PORT)/abacus
STACK_ENV = ABACUS_DATABASE_URL=postgresql+asyncpg://abacus_app:abacusapp@$(STACK_DB) \
	ABACUS_MIGRATIONS_DATABASE_URL=postgresql+asyncpg://abacus_owner:abacusowner@$(STACK_DB) \
	ABACUS_RELAY_DATABASE_URL=postgresql+asyncpg://abacus_relay:abacusrelay@$(STACK_DB) \
	ABACUS_IDENTITY_DATABASE_URL=postgresql+asyncpg://abacus_identity:abacusidentity@$(STACK_DB) \
	ABACUS_LOCAL_SUPERUSER_DSN=postgresql://postgres:postgres@$(STACK_DB) \
	ABACUS_S3_ENDPOINT_URL=http://127.0.0.1:$(ABACUS_S3_PORT) \
	ABACUS_TEMPORAL_TARGET=127.0.0.1:$(ABACUS_TEMPORAL_PORT)

# Local runs: the fake connector reads fixtures from here; seed_dev writes them (TASK-012).
LOCAL_ENV = $(STACK_ENV) ABACUS_FAKE_CONNECTOR_DIR=$(CURDIR)/backend/.local/fake-connector

# The API on :8001, the local sign-in server on :9000, the worker (relay + screening with the
# fake model) and the SPA on :5173, which proxies /v1 to the API; each port plus this checkout's
# offset. Ctrl-C, or any of them
# exiting, stops them all (polled: macOS's /bin/sh is bash 3.2, which has no `wait -n`). The ports
# are also set in apps/web/vite.config.ts (proxy), abacus_tools/fakes/oidc_server.py (HOST, PORT,
# REDIRECT_URIS) and .github/workflows/e2e.yml.
dev:
	docker compose up -d --wait db s3 temporal
	mkdir -p backend/.local/fake-connector
	cd backend && $(LOCAL_ENV) uv run alembic upgrade head && \
		$(LOCAL_ENV) uv run python -m abacus_tools.local.evidence_bucket
	cd backend; \
	export $(LOCAL_ENV); \
	export ABACUS_IDENTITY_JWKS="$$(uv run python -m abacus_tools.fakes.oidc_server --jwks)"; \
	trap 'kill 0' EXIT; \
	uv run python -m abacus_tools.fakes.oidc_server & oidc=$$!; \
	uv run uvicorn --factory abacus.api.app:create_app --port $(API_PORT) --reload & api=$$!; \
	uv run python -m abacus.worker & worker=$$!; \
	pnpm -C ../apps/web dev & web=$$!; \
	while kill -0 $$oidc $$api $$worker $$web 2>/dev/null; do sleep 1; done

# Dev firm and users for local sign-in; run again after creating an engagement to connect it.
seed: db-guard
	mkdir -p backend/.local/fake-connector
	cd backend && $(LOCAL_ENV) uv run python -m abacus_tools.local.seed_dev

# The Playwright journey (needs `make dev` running and `make seed` done); nightly in CI.
e2e:
	pnpm -C apps/web exec playwright test --project=chromium

check-fast:
	cd backend && uv lock --check
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run lint-imports
	cd backend && uv run python -m abacus_tools.quality.banned_patterns
	cd backend && uv run python -m abacus_tools.quality.error_codes
	cd backend && uv run python -m abacus_tools.quality.validate_docs
	cd backend && uv run python -m abacus_tools.quality.scope_guards
	$(MAKE) check-generated check-heads
	cd backend && uv run python -m abacus_tools.quality.secrets_scan
	cd backend && uv run python -m abacus_tools.quality.check_dependencies
	pnpm -C apps/web exec tsc --noEmit && pnpm -C apps/web exec eslint . && pnpm -C apps/web exec prettier --check .
	pnpm -C packages/ui exec tsc --noEmit && pnpm -C packages/ui exec eslint . && pnpm -C packages/ui exec prettier --check .
	pnpm -C apps/web exec vite build --logLevel warn
	pnpm -C apps/web exec node scripts/check-compiled-css.js dist
	pnpm -C apps/web exec node scripts/bundle-budget.mjs dist

# Generated files match their sources; never hand-edit one (F-01-T06). The API client's drift
# check stays in ci-contracts, which needs the OpenAPI export.
GENERATORS = permission_matrix feature_flags provider_terms agent_specs eval_suites status_vocabulary security_tests human_only_actions
check-generated:
	@cd backend && for g in $(GENERATORS); do \
		uv run python -m abacus_tools.codegen.$$g --check || { \
			echo "generated file out of date: run python -m abacus_tools.codegen.$$g"; exit 1; }; \
	done

# Every generated file, rebuilt from its source. Resolve a conflict in one by running this, never
# by picking a side (F-01-T09). Workflow replay histories are re-recorded per workflow instead.
regenerate:
	cd backend && for g in $(GENERATORS); do uv run python -m abacus_tools.codegen.$$g || exit 1; done
	$(MAKE) generate

# Local database targets refuse hosted databases (F-01-T09).
db-guard:
	@cd backend && $(STACK_ENV) uv run python -m abacus_tools.local.db_guard

# Give a linked worktree its own compose project and ports (F-01-T09); run once per worktree.
worktree-env:
	@cd backend && uv run python -m abacus_tools.local.worktree_env

# The SPA alone, on fixtures: no Docker, Python or Temporal (F-01-T09). F-04 and F-05 supply the
# fixture handlers behind VITE_FIXTURES.
dev-fixtures:
	VITE_FIXTURES=1 pnpm -C apps/web dev

# One migration head (F-01-T06): two migrations sharing a down_revision fail here.
check-heads:
	@cd backend && heads="$$(uv run alembic heads | grep -c '(head)')" && [ "$$heads" -eq 1 ] || { \
		echo "multiple heads: rebase onto origin/main and renumber (P-38)"; exit 1; }

check: check-fast
	cd backend && uv run pytest $(UNIT_TESTS) --cov --cov-fail-under=0
	cd backend && uv run pytest $(INTEGRATION_TESTS) --cov --cov-append --cov-fail-under=0
	cd backend && uv run python -m abacus_tools.ci.coverage_floor
	$(MAKE) ci-contracts ci-frontend

# CI stage 2 runs `check` as parallel jobs (TASK-017). Each suite is split into SHARDS by recorded
# run time (abacus_tools.ci.shard; every test file runs in exactly one shard), each shard keeps
# its own coverage data, and ci-coverage combines them and applies the floor. Refresh the timings
# after large test changes: pytest --durations=0 --durations-min=0 > report.txt, then
# python -m abacus_tools.ci.shard --record report.txt
UNIT_TESTS = tests/unit tests/property tests/acceptance
INTEGRATION_TESTS = tests/integration tests/security tests/workflows
SHARD ?= 1
SHARDS ?= 1

ci-unit:
	cd backend && files="$$(uv run python -m abacus_tools.ci.shard $(SHARD) $(SHARDS) $(UNIT_TESTS))" && \
		test -n "$$files" && COVERAGE_FILE=.coverage.unit-$(SHARD) \
		uv run pytest --cov --cov-report= --cov-fail-under=0 $$files

ci-integration:
	cd backend && files="$$(uv run python -m abacus_tools.ci.shard $(SHARD) $(SHARDS) $(INTEGRATION_TESTS))" && \
		test -n "$$files" && COVERAGE_FILE=.coverage.integration-$(SHARD) \
		uv run pytest --cov --cov-report= --cov-fail-under=0 $$files

# The floor (95) with DEC-10's dated exception, if any: backend/coverage-exception.toml.
ci-coverage:
	cd backend && uv run coverage combine && uv run python -m abacus_tools.ci.coverage_floor

ci-contracts:
	cd backend && uv run python -m abacus_tools.quality.schema_check
	cd backend && uv run python -m abacus_tools.contracts --check && uv run pytest tests/contracts
	@if [ -f backend/src/abacus/api/export_openapi.py ]; then \
		$(MAKE) generate && git diff --exit-code packages/api-client && \
		test -z "$$(git status --porcelain --untracked-files=all packages/api-client)"; \
	else echo "api-client drift: skipped until backend/src/abacus/api/export_openapi.py exists (TASK-008)"; fi

# The SPA's tests (F-01-T07: their own CI job, run when the frontend changes; vite build is stage 1).
ci-frontend:
	pnpm -C packages/ui test
	pnpm -C apps/web exec vitest run

# The gallery's visual run (F-05-T17): the specimen screenshot regression against $(BASE_SHA), parity
# Tier A and D. Needs a Playwright browser (pnpm -C apps/web exec playwright install chromium).
# Not part of `check`: CI's gallery job runs it when packages/ui or the gallery change.
ci-visual:
	pnpm -C apps/web run visual:ci

test:
	cd backend && uv run pytest

test-integration:
	cd backend && uv run pytest tests/integration

# Evaluation suites (SPEC-005): `make evals EVAL_ARGS="--agent evidence.screener --subset fast"`.
# Throwaway containers; exits non-zero unless the run passes. Without a model provider it runs on
# the fake model (a fake run proves the code paths, never a model's quality).
evals:
	cd backend && uv run python -m abacus_tools.evals $(EVAL_ARGS)

# SPEC-012: the quarterly break-glass access review (owner credentials). QUARTER=2026Q4
access-review:
	cd backend && uv run python -m abacus_tools.access_review --quarter $(QUARTER)

# SPEC-011: set a firm's feature flag (operators; audited).
flag:
	cd backend && uv run python -m abacus_tools.flags --firm $(FIRM) --flag $(FLAG) --value $(VALUE) --operator $(OPERATOR) --reason "$(REASON)"

# SPEC-010: the route parity check, with real credentials (costs a little). ROUTE=direct|bedrock
route-parity:
	cd backend && uv run python -m abacus_tools.route_parity --route $(ROUTE)

generate:
	cd backend && uv run python -m abacus.api.export_openapi > ../packages/api-client/openapi.json
	pnpm -C packages/api-client exec openapi-ts
	pnpm -C packages/api-client build:types

migrate: db-guard
	cd backend && $(STACK_ENV) uv run alembic upgrade head

# Not built yet: the load test arrives with Q-01 (OPS-16).
loadtest:
	@echo "not implemented: Q-01 OPS-16 (load test)" >&2; exit 1

# The Brightwater Hale scenario (F-04-T13): `make seed-demo SNAPSHOT=E0 HOLDOUT=fairhaven_ebp`.
# Loopback only; a second run writes nothing. NO_SETTLE=1 where no outbox relay runs.
SNAPSHOT ?= E0
HOLDOUT ?=
LOADER = abacus_tools.synthetic.scenarios.brightwater_hale.loader
LOADER_ARGS = --snapshot $(SNAPSHOT) $(foreach h,$(HOLDOUT),--holdout $(h)) $(if $(NO_SETTLE),--no-settle)
seed-demo: db-guard
	cd backend && $(LOCAL_ENV) uv run python -m $(LOADER) $(LOADER_ARGS)

# Staging demo tenant (F-04.17), run as the ECS one-off task after taking the deploy lock:
# `make seed-staging RESET_CLOCK=E0`. The loader refuses production, a real firm and a
# deploy-staging run in flight (it names the run). No db-guard: staging is hosted by design.
RESET_CLOCK ?= E0
seed-staging:
	cd backend && uv run python -m $(LOADER) --staging --snapshot $(RESET_CLOCK)

# Fixture JSON from the Python scenario arrives with F-04-T31 (S10); the TS seed is interim.
fixtures:
	@echo "not implemented: F-04-T31 (fixture export from the scenario)" >&2; exit 1

# Journeys (F-04 §3.8): fixture mode, gated on pull requests; full stack nightly, against
# `make dev` + `make seed-demo` with fakes and the injected clock, never a hosted database.
journeys:
	VITE_FIXTURES=1 ABACUS_JOURNEY_MODE=fixture pnpm -C apps/web exec playwright test --project=chromium --pass-with-no-tests e2e/journeys

journeys-full: db-guard
	ABACUS_JOURNEY_MODE=fullstack pnpm -C apps/web exec playwright test --project=chromium --pass-with-no-tests e2e/journeys
