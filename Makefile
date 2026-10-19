# The only command surface for humans, agents and CI (ADR-010). PROTECTED.
.PHONY: setup dev seed e2e check-fast check check-generated check-heads ci-unit ci-integration ci-coverage ci-contracts test test-integration evals generate migrate loadtest seed-staging route-parity flag access-review

setup:
	cd backend && uv sync --locked
	pnpm install --frozen-lockfile
	pnpm -C packages/api-client build:types

# Local runs: the fake connector reads fixtures from here; seed_dev writes them (TASK-012).
LOCAL_ENV = ABACUS_FAKE_CONNECTOR_DIR=$(CURDIR)/backend/.local/fake-connector

# The API on :8001, the local sign-in server on :9000, the worker (relay + screening with the
# fake model) and the SPA on :5173, which proxies /v1 to the API. Ctrl-C, or any of them
# exiting, stops them all (polled: macOS's /bin/sh is bash 3.2, which has no `wait -n`). The ports
# are also set in apps/web/vite.config.ts (proxy), abacus_tools/fakes/oidc_server.py (HOST, PORT,
# REDIRECT_URIS) and .github/workflows/e2e.yml.
dev:
	docker compose up -d --wait db s3 temporal
	mkdir -p backend/.local/fake-connector
	cd backend && uv run alembic upgrade head && uv run python -m abacus_tools.local.evidence_bucket
	cd backend; \
	export $(LOCAL_ENV); \
	export ABACUS_IDENTITY_JWKS="$$(uv run python -m abacus_tools.fakes.oidc_server --jwks)"; \
	trap 'kill 0' EXIT; \
	uv run python -m abacus_tools.fakes.oidc_server & oidc=$$!; \
	uv run uvicorn --factory abacus.api.app:create_app --port 8001 --reload & api=$$!; \
	uv run python -m abacus.worker & worker=$$!; \
	pnpm -C ../apps/web dev & web=$$!; \
	while kill -0 $$oidc $$api $$worker $$web 2>/dev/null; do sleep 1; done

# Dev firm and users for local sign-in; run again after creating an engagement to connect it.
seed:
	mkdir -p backend/.local/fake-connector
	cd backend && $(LOCAL_ENV) uv run python -m abacus_tools.local.seed_dev

# The Playwright journey (needs `make dev` running and `make seed` done); nightly in CI.
e2e:
	pnpm -C apps/web exec playwright test

check-fast:
	cd backend && uv lock --check
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run lint-imports
	cd backend && uv run python -m abacus_tools.quality.banned_patterns
	cd backend && uv run python -m abacus_tools.quality.validate_docs
	$(MAKE) check-generated check-heads
	cd backend && uv run python -m abacus_tools.quality.secrets_scan
	cd backend && uv run python -m abacus_tools.quality.check_dependencies
	pnpm -C apps/web exec tsc --noEmit && pnpm -C apps/web exec eslint . && pnpm -C apps/web exec prettier --check .
	pnpm -C packages/ui exec tsc --noEmit && pnpm -C packages/ui exec eslint . && pnpm -C packages/ui exec prettier --check .
	pnpm -C apps/web exec vite build --logLevel warn

# Generated files match their sources; never hand-edit one (F-01-T06). The API client's drift
# check stays in ci-contracts, which needs the OpenAPI export.
GENERATORS = permission_matrix feature_flags provider_terms agent_specs eval_suites
check-generated:
	@cd backend && for g in $(GENERATORS); do \
		uv run python -m abacus_tools.codegen.$$g --check || { \
			echo "generated file out of date: run python -m abacus_tools.codegen.$$g"; exit 1; }; \
	done

# One migration head (F-01-T06): two migrations sharing a down_revision fail here.
check-heads:
	@cd backend && heads="$$(uv run alembic heads | grep -c '(head)')" && [ "$$heads" -eq 1 ] || { \
		echo "multiple heads: rebase onto origin/main and renumber (P-38)"; exit 1; }

check: check-fast
	cd backend && uv run pytest $(UNIT_TESTS) --cov --cov-fail-under=0
	cd backend && uv run pytest $(INTEGRATION_TESTS) --cov --cov-append
	$(MAKE) ci-contracts

# CI stage 2 runs `check` as parallel jobs (TASK-017). Each suite is split into SHARDS by recorded
# run time (abacus_tools.ci.shard; every test file runs in exactly one shard), each shard keeps
# its own coverage data, and ci-coverage combines them and applies the floor. Refresh the timings
# after large test changes: pytest --durations=0 --durations-min=0 > report.txt, then
# python -m abacus_tools.ci.shard --record report.txt
UNIT_TESTS = tests/unit tests/property
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

ci-coverage:
	cd backend && uv run coverage combine && uv run coverage report

ci-contracts:
	cd backend && uv run python -m abacus_tools.quality.schema_check
	@if [ -f backend/src/abacus/api/export_openapi.py ]; then \
		$(MAKE) generate && git diff --exit-code packages/api-client && \
		test -z "$$(git status --porcelain --untracked-files=all packages/api-client)"; \
	else echo "api-client drift: skipped until backend/src/abacus/api/export_openapi.py exists (TASK-008)"; fi
	pnpm -C apps/web exec vitest run

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

migrate:
	cd backend && uv run alembic upgrade head

loadtest:
	cd backend && uv run python -m abacus_tools.loadtest.run --profile $(PROFILE)

seed-staging:
	cd backend && uv run python -m abacus_tools.synthetic.seed --profile $(PROFILE)
