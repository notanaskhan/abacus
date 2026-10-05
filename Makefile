# The only command surface for humans, agents and CI (ADR-010). PROTECTED.
.PHONY: setup dev check-fast check test test-integration evals generate migrate loadtest seed-staging

setup:
	cd backend && uv sync --locked
	pnpm install --frozen-lockfile

dev:
	docker compose up -d db minio temporal
	cd backend && uv run uvicorn abacus.api.main:app --reload & \
	cd backend && uv run python -m abacus.worker.main & \
	pnpm -C apps/web dev

check-fast:
	cd backend && uv lock --check
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run lint-imports
	cd backend && uv run python -m abacus_tools.quality.banned_patterns
	cd backend && uv run python -m abacus_tools.quality.validate_docs
	cd backend && uv run python -m abacus_tools.quality.secrets_scan
	cd backend && uv run python -m abacus_tools.quality.check_dependencies
	pnpm -C apps/web exec tsc --noEmit && pnpm -C apps/web exec eslint . && pnpm -C apps/web exec prettier --check .

check: check-fast
	cd backend && uv run pytest tests/unit tests/property --cov --cov-fail-under=0
	cd backend && uv run pytest tests/integration tests/security tests/workflows --cov --cov-append
	cd backend && uv run python -m abacus_tools.quality.schema_check
	@if [ -f backend/src/abacus/api/main.py ]; then \
		$(MAKE) generate && git diff --exit-code packages/api-client; \
	else echo "api-client drift: skipped until backend/src/abacus/api/main.py exists (SPEC-000)"; fi
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

migrate:
	cd backend && uv run alembic upgrade head

loadtest:
	cd backend && uv run python -m abacus_tools.loadtest.run --profile $(PROFILE)

seed-staging:
	cd backend && uv run python -m abacus_tools.synthetic.seed --profile $(PROFILE)
