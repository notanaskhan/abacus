# Protected paths

Solo edition (2026-10-20, SU-06). One builder works through Claude Code with no approval files, no code owners and no review gate. The local hooks in `.claude/hooks/` keep only the guards that protect data and correctness; `make check` is the gate before merging.

| Layer | Where | What it does |
|---|---|---|
| Edit hook | `.claude/hooks/protect_paths.py` (rules in `_protected.py`) | Blocks agent edits to secret files, generated files and migrations already on `origin/main` |
| Shell hook | `.claude/hooks/guard_bash.py` | Blocks destructive or unsafe commands (below) |
| Checks | `make check-fast`, `make check` | Lint, types, import rules, generated-file drift, single migration head, secrets scan, tests |
| `main` ruleset | GitHub settings | No force pushes, no deletion, linear history |

## Never edited by an agent

- **Secrets:** `.env`, `.env.*` (templates `.env.example`, `.env.sample` and `.env.template` are fine), `*.pem`, `*.key`, `*.p12`, `*.pfx`, any `secrets/` directory, `credentials` files. Edit these yourself, outside the session. Never commit them: the repository is public.
- **Generated files:** `packages/api-client/openapi.json` and `packages/api-client/src/**` (`make generate`), `_matrix.py`, `_flags.py`, `_provider_terms.py`, `_human_only_actions.py`, `_specs.py`, `_eval_suites.py`, `integrations/_capabilities.py` (from `docs/architecture/write-capabilities.yaml`, A-02-T15), `docs/operations/sub-processors.md` (their `abacus_tools.codegen` module or `make regenerate`), `backend/tests/durations.json`, workflow replay histories. Regenerate instead; resolve a conflict in one by regenerating, never by picking a side.
- **Applied migrations:** a file in `backend/migrations/versions/` that is already on `origin/main`. Add a new migration instead; keep one Alembic head. A migration that exists only on your branch can still be edited.

## Only raised

- **Mutation floors:** `backend/mutation-thresholds.yaml` (Q-03-T027; QD-4; ADR-079; DEC-365). The edit hook rebuilds the file as an Edit, MultiEdit or Write would leave it and refuses a floor that is lower than on disk or on `origin/main`, a removed scope, or a file it cannot parse; the shell hook refuses any shell write to it. CI refuses the same: `python -m abacus_tools.quality.mutation_floors` in `make check-fast` (against `origin/main` when the checkout has it) and in `mutation-floors.yml` (against the pull request's base). Raising a floor or adding a scope is a normal change; AY approves. The mutation scope is protected with the floors: the edit hook refuses an agent edit to `[tool.mutmut]` in `backend/pyproject.toml` or `SCOPES` in `abacus_tools/quality/mutation.py`, and the guard refuses any narrowing against the base; `mutation-floors.yml` runs the base commit's guard.
- **Coverage floors:** `backend/coverage-thresholds.yaml` (Q-03-T066; ADR-079; DEC-907): a line and a branch floor per red module beside the global `fail_under`. CI refuses a lower or removed floor (`python -m abacus_tools.quality.coverage_floors` in `make check-fast`, against `origin/main`) and stage 2 fails a red module under its floor (`--measure` in `make ci-coverage`). Raising a floor is a normal change; AY approves.
- **Supply-chain findings register:** `docs/quality/supply-chain-findings.yaml` (Q-03-T029; DEC-366) is written by a person, never an agent; on a pull request the scanners' ignores come from the base's copy and a loosened register fails `security findings SLA`.

The hooks are a guardrail against agent mistakes, not a security boundary: CI is the enforcement.

## Shell commands the hook refuses

Force pushes; `git commit --no-verify`; recursive deletion of root, home or the project; `sudo`; `chmod 777`; `terraform destroy`, `import` and `state`; `psql`, `pg_dump` and `pg_restore` against a non-local host; AWS production profiles; direct calls to model provider APIs (use `ai_gateway`); `alembic downgrade` against staging or production; `git checkout --ours/--theirs` on a generated file; any write to `backend/mutation-thresholds.yaml`.

## Still binding, as rules rather than locks

The policy files keep their meaning and are changed deliberately, in the same change as the code that needs them: the permission matrix, the dependency allowlist, the glossary, the failure taxonomy, the coverage floor, evaluation suites, cost baselines and judge calibration, the provider terms register, the sub-processor register (`docs/operations/sub-processors.yaml`, P-67: a Terraform egress host without a row fails `make check-generated`), the data-classification vocabulary (`backend/src/abacus/kernel/classification.py`, Q-02-T06), the evaluation baselines (`evals/baselines.yaml` once it exists; Q-02-T06), and the write-capability registry (`docs/architecture/write-capabilities.yaml`, A-02-T15, ADR-150: every read connector's egress hosts and the reserved writes; v1 enables none, and a change is a reviewed policy change that regenerates `_capabilities.py`), the release-window calendar (`deploy/windows.yaml`, Q-04-T002, P-29: both founders approve every change; `make check-fast` checks its dates against the rule and refuses any firm that is not a pilot code), the human-only actions register (`docs/architecture/human-only-actions.yaml`, Q-02-T17: a change also needs a migration redefining `abacus_human_only_actions()`), and the fresh-MFA list (`docs/architecture/fresh-mfa-actions.yaml`, Q-02-T30: every listed action carries `mfa_recent: required`, checked by `tests/unit/quality/test_fresh_mfa_actions.py`, the lint `abacus_tools.quality.fresh_mfa` and the generated overlay; its floor is the hand-kept `tests/unit/quality/test_fresh_mfa_minimum.py`, PROTECTED: shrinking it is a reviewed change, never a regeneration). Accepted ADRs are superseded by a new ADR rather than rewritten; `validate_docs` checks the supersede chain.

## Tax red files (T-01-T07, DEC-1158)
The solo edition keeps no approval hook (SU-06), so red files are named here and in the module README rather than enforced by `.claude/hooks/_protected.py`: `backend/src/abacus/modules/organisations/consent*.py`, `organisations/tax_profile.py`, and `backend/src/abacus/modules/tax/{approval,export,filing,tri,tax_profile,k1_release,k1_release_workflow}.py` (`tax_profile.py`: T-01-T43, DEC-1651) (`approval.py` is the only writer of a tax return's `final_approval` sign-off, enforced by TAXAPPROVE-001; `k1_release.py` the only writer of `k1_releases`, K1RELEASE-001, T-02-T21). Changing one needs the security review of a red diff. NEVER-ERO-001 refuses any IRS e-file channel or ERO/transmitter identifier in product code.

## Sampler compute and the frozen corpus (A-03-T01, DEC-1550; ADR-340)
A frozen sampler version can never be "fixed" by a session: new behaviour ships only as a new
`SAMPLER_VERSIONS` entry. These are red files, named here and in `sampling/README.md`:
`backend/src/abacus/modules/sampling/compute/**` and `backend/tests/golden/sampling/corpus/**`.
The compute packages (`sampling/compute`, `ledger/compute`) import only `abacus.kernel.numeric`
and `abacus.kernel.calendar`; the import-linter contract that says so is switched on by A-03-T21,
which adds `backend/src/abacus/kernel/numeric.py` and `backend/src/abacus/kernel/calendar.py` to
the red files.
