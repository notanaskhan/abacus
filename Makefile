# The only command surface for humans, agents and CI (ADR-010). PROTECTED.
.PHONY: setup dev check-fast check test test-integration evals generate migrate loadtest seed-staging

setup:
	cd backend && uv sync
	pnpm install --frozen-lockfile

dev:
	docker compose up -d db minio temporal
	cd backend && uv run uvicorn app.main:app --reload & \
	cd backend && uv run python -m worker.main & \
	pnpm -C apps/web dev

check-fast:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run lint-imports
	cd backend && uv run python -m quality.banned_patterns
	cd backend && uv run python -m quality.validate_docs
	pnpm -C apps/web exec tsc --noEmit && pnpm -C apps/web exec eslint . && pnpm -C apps/web exec prettier --check .

check: check-fast
	cd backend && uv run pytest tests/unit tests/property
	cd backend && uv run pytest tests/integration tests/security tests/workflows
	cd backend && uv run python -m quality.schema_check
	$(MAKE) generate && git diff --exit-code packages/api-client
	pnpm -C apps/web exec vitest run

test:
	cd backend && uv run pytest

test-integration:
	cd backend && uv run pytest tests/integration

evals:
	cd backend && uv run pytest ../evals

generate:
	cd backend && uv run python -m app.export_openapi > ../packages/api-client/openapi.json
	pnpm -C packages/api-client exec openapi-ts

migrate:
	cd backend && uv run alembic upgrade head

loadtest:
	cd backend && uv run python -m loadtest.run --profile $(PROFILE)

seed-staging:
	cd backend && uv run python -m synthetic.seed --profile $(PROFILE)
