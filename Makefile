# The only command surface for humans, agents and CI (ADR-010). PROTECTED.
.PHONY: setup dev seed e2e check-fast check test test-integration evals generate migrate loadtest seed-staging

setup:
	cd backend && uv sync --locked
	pnpm install --frozen-lockfile
	pnpm -C packages/api-client build:types

# Local runs: the fake connector reads fixtures from here; seed_dev writes them (TASK-012).
LOCAL_ENV = ABACUS_FAKE_CONNECTOR_DIR=$(CURDIR)/backend/.local/fake-connector

# The API on :8001, the local sign-in server on :9000, the worker (relay + screening with the
# fake model) and the SPA on :5173, which proxies /v1 to the API. Ctrl-C, or any of them
# exiting, stops them all. The ports are also set in apps/web/vite.config.ts (proxy),
# abacus_tools/fakes/oidc_server.py (HOST, PORT, REDIRECT_URIS) and .github/workflows/e2e.yml.
dev:
	docker compose up -d --wait db s3 temporal
	mkdir -p backend/.local/fake-connector
	cd backend && uv run alembic upgrade head && uv run python -m abacus_tools.local.evidence_bucket
	cd backend; \
	export $(LOCAL_ENV); \
	export ABACUS_IDENTITY_JWKS="$$(uv run python -m abacus_tools.fakes.oidc_server --jwks)"; \
	trap 'kill 0' EXIT; \
	uv run python -m abacus_tools.fakes.oidc_server & \
	uv run uvicorn --factory abacus.api.app:create_app --port 8001 --reload & \
	uv run python -m abacus.worker & \
	pnpm -C ../apps/web dev & \
	wait -n

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
	cd backend && uv run python -m abacus_tools.quality.secrets_scan
	cd backend && uv run python -m abacus_tools.quality.check_dependencies
	pnpm -C apps/web exec tsc --noEmit && pnpm -C apps/web exec eslint . && pnpm -C apps/web exec prettier --check .
	pnpm -C packages/ui exec tsc --noEmit && pnpm -C packages/ui exec eslint . && pnpm -C packages/ui exec prettier --check .

check: check-fast
	cd backend && uv run pytest tests/unit tests/property --cov --cov-fail-under=0
	cd backend && uv run pytest tests/integration tests/security tests/workflows --cov --cov-append
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

evals:
	cd backend && uv run pytest ../evals

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
