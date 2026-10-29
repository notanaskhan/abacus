# The only command surface for humans, agents and CI (ADR-010). PROTECTED.
.PHONY: backfill-rerun shadow-report pilot-metrics go-live-check windows flag-calendar agent-stage setup dev seed e2e check-fast check check-generated check-heads regenerate db-guard worktree-env dev-fixtures ci-unit ci-integration ci-coverage ci-contracts ci-frontend ci-visual test test-integration evals evals-review-fast evals-match-fast generate migrate loadtest seed-demo seed-staging fixtures journeys journeys-full route-parity flag access-review audit-chain-verify entitlement incident-propagate incident-status schedules deploy-lock release-check release-pr

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
	export ABACUS_IDENTITY_CLIENT_ID=abacus-web \
		ABACUS_IDENTITY_AUTHORIZE_URL=http://127.0.0.1:$(call port,9000)/authorize \
		ABACUS_IDENTITY_EXCHANGE_URL=http://127.0.0.1:$(call port,9000)/token \
		ABACUS_WEB_ORIGIN=http://localhost:$(call port,5173); \
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
	cd backend && uv run python -m abacus_tools.quality.seed_contamination
	cd backend && uv run python -m abacus_tools.quality.fresh_mfa
	# Q-03-T095 (ADR-080): every table and matrix kind the code uses has its generated tests.
	cd backend && uv run python -m abacus_tools.quality.generator_coverage
	# Q-03-T097: at most 5 flaky tests in quarantine, none past 10 working days.
	cd backend && uv run python -m abacus_tools.quality.quarantine
	# Q-03-T094: the fakes register names real files (unverified fakes are reported, not failed).
	cd backend && uv run python -m abacus_tools.quality.fakes
	cd backend && uv run python -m abacus_tools.quality.mutation_floors
	cd backend && uv run python -m abacus_tools.quality.coverage_floors
	cd backend && uv run python -m abacus_tools.release_windows check
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
GENERATORS = permission_matrix role_templates feature_flags provider_terms ai_policy_defaults agent_specs eval_suites status_vocabulary security_tests human_only_actions sub_processors export_manifest_schema write_capabilities
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
	cd backend && uv run pytest $(XDIST) $(UNIT_TESTS) --cov --cov-fail-under=0
	cd backend && uv run pytest $(XDIST_INTEGRATION) $(INTEGRATION_TESTS) --cov --cov-append --cov-fail-under=0
	cd backend && uv run pytest $(SERIAL) $(UNIT_TESTS) $(INTEGRATION_TESTS) --cov --cov-append --cov-fail-under=0
	cd backend && uv run python -m abacus_tools.ci.coverage_floor
	$(MAKE) evals-review-fast
	$(MAKE) evals-match-fast
	$(MAKE) ci-contracts ci-frontend

# CI stage 2 runs `check` as parallel jobs (TASK-017). Each suite is split into SHARDS by recorded
# run time (abacus_tools.ci.shard; every test file runs in exactly one shard), each shard keeps
# its own coverage data, and ci-coverage combines them and applies the floor. Refresh the timings
# after large test changes, in one process (workers would skew them and charge each worker's
# container start to whichever file it ran first):
# pytest -n 0 --durations=0 --durations-min=0 > report.txt, then
# python -m abacus_tools.ci.shard --record report.txt
UNIT_TESTS = tests/unit tests/property tests/acceptance tests/connectors
INTEGRATION_TESTS = tests/integration tests/security tests/workflows
SHARD ?= 1
SHARDS ?= 1

# Parallel test workers (pytest-xdist, DEC-335). PYTEST_WORKERS is a count or `auto` (one per
# core); 0 runs in one process, as before. Each worker is its own pytest session, so the
# integration and security suites start their own Postgres, S3 and Temporal containers per worker:
# PYTEST_INTEGRATION_WORKERS caps those (default 4). Tests go to whichever worker is free
# (loadgroup), except that tests marked `xdist_group(name=...)` share one worker. Not loadfile:
# one 340 s file (test_identity.py) would set a whole integration shard's time.
PYTEST_WORKERS ?= auto
PYTEST_INTEGRATION_WORKERS ?= 4
XDIST = -n $(PYTEST_WORKERS) --dist loadgroup -m "not serial"
XDIST_INTEGRATION = -n $(PYTEST_INTEGRATION_WORKERS) --dist loadgroup -m "not serial"
# Wall-clock budget tests (`@pytest.mark.serial`) run after the workers, alone, so contention
# never decides them (DEC-335). Exit 5 is pytest's "nothing collected" for a shard without one.
SERIAL = -n 0 -m serial

ci-unit:
	cd backend && files="$$(uv run python -m abacus_tools.ci.shard $(SHARD) $(SHARDS) $(UNIT_TESTS))" && \
		test -n "$$files" && COVERAGE_FILE=.coverage.unit-$(SHARD) \
		uv run pytest $(XDIST) --cov --cov-report= --cov-fail-under=0 $$files && \
		{ COVERAGE_FILE=.coverage.unit-$(SHARD) uv run pytest $(SERIAL) --cov --cov-append \
			--cov-report= --cov-fail-under=0 $$files || [ $$? -eq 5 ]; }

ci-integration:
	cd backend && files="$$(uv run python -m abacus_tools.ci.shard $(SHARD) $(SHARDS) $(INTEGRATION_TESTS))" && \
		test -n "$$files" && COVERAGE_FILE=.coverage.integration-$(SHARD) \
		uv run pytest $(XDIST_INTEGRATION) --cov --cov-report= --cov-fail-under=0 $$files && \
		{ COVERAGE_FILE=.coverage.integration-$(SHARD) uv run pytest $(SERIAL) --cov --cov-append \
			--cov-report= --cov-fail-under=0 $$files || [ $$? -eq 5 ]; }

# The floor (95) with DEC-10's dated exception, if any: backend/coverage-exception.toml.
ci-coverage:
	cd backend && uv run coverage combine && uv run python -m abacus_tools.ci.coverage_floor
	cd backend && uv run python -m abacus_tools.quality.coverage_floors --measure

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

# Every suite under backend/tests, in two runs: those without containers on PYTEST_WORKERS, then
# those with them (the contracts' undo suite has its own database) on PYTEST_INTEGRATION_WORKERS.
# PYTEST_WORKERS=0 PYTEST_INTEGRATION_WORKERS=0 make test runs each in one process.
test:
	cd backend && uv run pytest $(XDIST) $(UNIT_TESTS) tests/golden
	cd backend && uv run pytest $(XDIST_INTEGRATION) tests/contracts $(INTEGRATION_TESTS)
	cd backend && uv run pytest $(SERIAL) $(UNIT_TESTS) $(INTEGRATION_TESTS)

test-integration:
	cd backend && uv run pytest $(XDIST_INTEGRATION) tests/integration
	cd backend && uv run pytest $(SERIAL) tests/integration

# Evaluation suites (SPEC-005): `make evals EVAL_ARGS="--agent evidence.screener --subset fast"`.
# Throwaway containers; exits non-zero unless the run passes. Without a model provider it runs on
# the fake model (a fake run proves the code paths, never a model's quality).
evals:
	cd backend && uv run python -m abacus_tools.evals $(EVAL_ARGS)

# P-06-T21: the upload reviewer's fast run on the fake model's recorded answers (every case once,
# throwaway containers, no model call, no cost). Part of `check`; CI's stage 3 runs it too.
evals-review-fast:
	cd backend && uv run python -m abacus_tools.evals --agent evidence.upload_reviewer --route fake --subset fast

# N-01-T21: the matcher's intake section on its recorded answers (extraction, the content rules and
# the file-name baseline run for real; the matcher's answer is recorded, no model call, no cost).
evals-match-fast:
	cd backend && uv run python -m abacus_tools.evals --agent evidence.matcher --route fake --section intake

# SPEC-012: the quarterly break-glass access review (owner credentials). QUARTER=2026Q4
access-review:
	cd backend && uv run python -m abacus_tools.access_review --quarter $(QUARTER)

# Q-02-T21: recompute a firm's audit checkpoints from their rows; exits 1 on any mismatch.
audit-chain-verify:
	cd backend && uv run python -m abacus_tools.audit_chain verify --tenant $(TENANT)

# Q-02-T07 (SPEC-036 Q1, Q3): an agent's shadow report for a firm, or set its stage (founder, owner
# credentials; audited). `make agent-stage FIRM=<id> AGENT=evidence.screener` reports;
# add STAGE=shadow|live|off NOTE="..." to set (the note reaches the command as an environment
# variable, never as shell text). Staff use PUT /v1/platform/agent-stages instead.
agent-stage: export AGENT_STAGE_NOTE := $(NOTE)
agent-stage:
	cd backend && uv run python -m abacus_tools.agent_stage $(if $(STAGE),set $(FIRM) $(AGENT) $(STAGE) "$$AGENT_STAGE_NOTE" $(if $(REPORT_SHA),$(REPORT_SHA) $(REPORT_AS_OF)),report $(FIRM) $(AGENT))

# Q-02-T50 (DEC-811): the deterministic shadow score for one firm and agent, as JSON with its SHA-256;
# `make agent-stage ... STAGE=live REPORT_SHA=<sha256> REPORT_AS_OF=<as_of>` names it to go live.
shadow-report:
	cd backend && uv run python -m abacus_tools.agent_stage score $(FIRM) $(AGENT)

# SPEC-011: set a firm's feature flag (operators; audited).
# Q-04-T004 (P-29): a pilot firm's flip names APPROVED_BY (never the operator) and ROLLBACK; inside its
# window also REQUEST (the ops-request file) and the Tuesday slot, or HOTFIX="<reason>"; a prompt.*
# variant also EVAL_REPORT and SHADOW_RUN. ALL_OFF=1 sets every flag for the firm to its default.
flag:
	cd backend && uv run python -m abacus_tools.flags --firm $(FIRM) $(if $(ALL_OFF),--all-off,--flag $(FLAG) --value $(VALUE)) --operator $(OPERATOR) --reason "$(REASON)" $(if $(APPROVED_BY),--approved-by $(APPROVED_BY)) $(if $(ROLLBACK),--rollback "$(ROLLBACK)") $(if $(REQUEST),--request $(REQUEST)) $(if $(HOTFIX),--hotfix "$(HOTFIX)") $(if $(EVAL_REPORT),--eval-report "$(EVAL_REPORT)") $(if $(SHADOW_RUN),--shadow-run "$(SHADOW_RUN)")

# Q-02-T33 (RB-27): propagate an Accrued incident into the firms it touched, as staff. Needs
# ABACUS_STAFF_TOKEN (a staff-issuer token with MFA) in the environment; STAFF must be the id it
# proves. DRY_RUN=1 checks and starts nothing. FACTS is a JSON file of Accrued's facts (never
# committed). `make incident-status REF=…` prints the staff record: requests, refusals, failed firms.
incident-propagate:
	cd backend && uv run python -m abacus_tools.incidents propagate --ref $(REF) --firms $(FIRMS) --facts $(FACTS) --staff $(STAFF) --reason "$(REASON)" $(if $(DRY_RUN),--dry-run)

incident-status:
	cd backend && uv run python -m abacus_tools.incidents status --ref $(REF)

# Q-04-T005 (P-29; RK-15): every flag with owner, expiry, the last release train before it, the
# window it expires in (or its window_exception) and a 21-day warning. Read-only.
flag-calendar:
	@cd backend && uv run python -m abacus_tools.codegen.feature_flags --calendar

# Q-04-T009: the dossier's evidence for one firm at one level, as JSON (exit 1 when an item fails).
# An ops task in production, read-only. LEVEL=shadow|client_facing|tax|season; AT=<ISO> to look ahead.
go-live-check:
	cd backend && uv run python -m abacus_tools.go_live --firm $(FIRM) --level $(LEVEL) $(if $(AT),--at $(AT))

# Q-04-T002 (P-29): the release-window calendar from deploy/windows.yaml, all years or YEAR=2027.
windows:
	@cd backend && uv run python -m abacus_tools.release_windows calendar $(if $(YEAR),--year $(YEAR))

# Q-01-T45: change one firm's module entitlement (ops task; audited as the operator).
entitlement:
	cd backend && uv run python -m abacus_tools.tenants entitlement --firm $(FIRM) --module $(MODULE) --enabled $(ENABLED) $(if $(SEATS),--seats $(SEATS)) --operator $(OPERATOR) --reason "$(REASON)" $(if $(APPROVED_BY),--approved-by $(APPROVED_BY)) $(if $(ROLLBACK),--rollback "$(ROLLBACK)") $(if $(REQUEST),--request $(REQUEST)) $(if $(HOTFIX),--hotfix "$(HOTFIX)")

# Q-04-T007: enrol a work item in a pilot window (shadow), or move its mode (operators; audited).
pilot-enrol:
	cd backend && uv run python -m abacus_tools.pilots enrol --firm $(FIRM) --work-item $(WORK_ITEM) --start $(START) --end $(END) $(if $(BASELINE_DAYS),--baseline-days $(BASELINE_DAYS)) --operator $(OPERATOR)

pilot-mode:
	cd backend && uv run python -m abacus_tools.pilots mode --firm $(FIRM) --enrolment $(ENROLMENT) --mode $(MODE) --operator $(OPERATOR) $(if $(CONFIRMED_BY),--confirmed-by $(CONFIRMED_BY))

# Q-04-T008: compute (or rerun, idempotently) one firm's pilot metrics for the ISO week starting WEEK (a Monday).
pilot-metrics:
	cd backend && uv run python -m abacus_tools.pilots metrics --firm $(FIRM) --week $(WEEK)

# Q-01-T26: create or converge the platform-job Schedules (spend anomaly, notification purge) on
# the local stack's Temporal only (--local-only refuses any other). Idempotent; the deploys run it
# as an ops task after migrate.
schedules:
	cd backend && uv run python -m abacus_tools.schedules ensure --local-only

# Q-01-T18 (platform-ops contract 3.4): who holds an environment's deploy lock, and for how long.
# Read only: it never takes or releases the lock. ENV=staging|production
deploy-lock:
	@cd backend && uv run python -m abacus_tools.deploy_lock show --env $(ENV)

# Q-01-T34: open the release PR for a staging-verified SHA. Needs a shared-account read session
# (AWS_PROFILE) and gh. Merging the PR runs deploy-production.yml.
# Q-04-T003 (P-29): the release window gate on the committed (or AT=<ISO instant>) release record,
# locally and read-only: window_mode, rollback, the Tuesday slot, deadline weeks, the migrate hold.
release-check:
	cd backend && uv run python -m abacus_tools.release window-gate --release ../deploy/production/release.json $(if $(AT),--at $(AT))

release-pr:
	@test -n "$(SHA)" || (echo "usage: make release-pr SHA=<40-character git sha>"; exit 2)
	aws s3 cp s3://abacus-shared-artifacts/releases/$(SHA)/release.json deploy/production/release.json
	cd backend && uv run python -m abacus_tools.release check ../deploy/production/release.json --production
	git switch -c release/$(SHA)
	git add deploy/production/release.json
	git commit -m "release: promote $(SHA) to production"
	git push -u origin release/$(SHA)
	gh pr create --title "Release $(SHA)" --body "Promotes $(SHA) (deploy/production/release.json). deploy-production.yml checks the staging-verified, replay and Inspector gates."

# Q-03-T059: re-run the 44 back-filled suites and write docs/quality/backfill-rerun-<date>.md.
backfill-rerun:
	cd backend && uv run python -m abacus_tools.quality.backfill_rerun

# SPEC-010: the route parity check, with real credentials (costs a little). ROUTE=direct|bedrock
route-parity:
	cd backend && uv run python -m abacus_tools.route_parity --route $(ROUTE)

generate:
	cd backend && uv run python -m abacus.api.export_openapi > ../packages/api-client/openapi.json
	pnpm -C packages/api-client exec openapi-ts
	pnpm -C packages/api-client build:types

migrate: db-guard
	cd backend && $(STACK_ENV) uv run alembic upgrade head

# The load-test harness (Q-03-T035): `make loadtest PROFILE=smoke` plays
# backend/src/abacus_tools/loadtest/scenarios/$(PROFILE).yaml against this checkout's local stack
# (`make dev` and `make seed` running) and writes p50/p95/p99 per endpoint group under
# backend/.local/loadtest/. Loopback targets only; never a hosted environment or database.
# Q-03-T044: the journey profiles (`journeys`, `pbc_import_burst`) read the Brightwater Hale ids
# from `abacus_tools.loadtest.journey_vars` (needs `make seed-demo`); VARS adds more NAME=VALUE.
# Q-03-T043: DRY_RUN=1 prints the plan and sends nothing (`make loadtest PROFILE=monday_9am DRY_RUN=1`).
PROFILE ?= smoke
VARS ?=
loadtest:
	cd backend && $(LOCAL_ENV) uv run python -m abacus_tools.loadtest.run --profile $(PROFILE) \
		--base-url http://127.0.0.1:$(API_PORT) --temporal-target 127.0.0.1:$(ABACUS_TEMPORAL_PORT) \
		$$(uv run python -m abacus_tools.loadtest.journey_vars) $(foreach v,$(VARS),--var $(v)) \
		$(if $(DRY_RUN),--dry-run)

# The Brightwater Hale scenario (F-04-T13): `make seed-demo SNAPSHOT=E0 HOLDOUT=fairhaven_ebp`.
# Loopback only; a second run writes nothing. NO_SETTLE=1 where no outbox relay runs.
# SLICE adds opt-in slices to audit_core, e.g. `make seed-demo SLICE=compliance` (Q-02-T39).
SNAPSHOT ?= E0
HOLDOUT ?=
SLICE ?=
LOADER = abacus_tools.synthetic.scenarios.brightwater_hale.loader
LOADER_ARGS = --snapshot $(SNAPSHOT) $(foreach h,$(HOLDOUT),--holdout $(h)) $(foreach s,$(SLICE),--slice $(s)) $(if $(NO_SETTLE),--no-settle)
seed-demo: db-guard
	cd backend && $(LOCAL_ENV) uv run python -m $(LOADER) $(LOADER_ARGS)

# Staging demo tenant (F-04.17), run as the ECS one-off task after taking the deploy lock:
# `make seed-staging RESET_CLOCK=E0`. The loader refuses production, a real firm and a
# deploy-staging run in flight (it names the run). No db-guard: staging is hosted by design.
# The portal slice (P-08-T14, with the binders it needs) gives staging the branded portal host
# `brightwaterhale.<portal_base_domain>` and every portal persona; it refuses without the domain.
# Load profiles (Q-03-T044): `make seed-staging PROFILE=x1|x25|x100` builds that many synthetic
# Brightwater-size firms (abacus_tools.synthetic.fleet) instead, on the perf stack (QD-6), with
# the same refusals. Any other PROFILE (the loadtest default `smoke`) seeds Brightwater Hale.
RESET_CLOCK ?= E0
FLEET_PROFILE = $(filter x1 x25 x100,$(PROFILE))
seed-staging:
ifneq ($(FLEET_PROFILE),)
	cd backend && uv run python -m abacus_tools.synthetic.fleet --staging --profile $(FLEET_PROFILE)
else
	cd backend && uv run python -m $(LOADER) --staging --snapshot $(RESET_CLOCK) --slice portal
endif

# F-04-T31 (F-04.21): fixture JSON exported from the Python scenario at a snapshot, through the
# API, into apps/web/src/fixtures/seed/exported/<SNAPSHOT>/. Throwaway Postgres (Docker), never
# a hosted or the developer's database. The TS seed stays for the paths not exported yet.
fixtures:
	cd backend && uv run python -m abacus_tools.synthetic.fixture_export --snapshot $(SNAPSHOT)

# Journeys (F-04 §3.8): fixture mode, gated on pull requests; full stack nightly, against
# `make dev` + `make seed-demo` with fakes and the injected clock, never a hosted database. The
# harness (F-04-T21) gives each its Playwright project and persona adapter; ABACUS_FIXTURES=1 starts
# the fixture server. Staging and canary are `--project=staging` / `canary` with their URL set.
# JOURNEY_ARGS passes Playwright options through (CI: `--trace=on`, F-04-T28).
JOURNEY_ARGS ?=
journeys:
	ABACUS_FIXTURES=1 pnpm -C apps/web exec playwright test --project=fixture $(JOURNEY_ARGS)

journeys-full: db-guard
	pnpm -C apps/web exec playwright test --project=fullstack $(JOURNEY_ARGS)
