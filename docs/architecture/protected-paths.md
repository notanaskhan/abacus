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
- **Generated files:** `packages/api-client/openapi.json` and `packages/api-client/src/**` (`make generate`), `_matrix.py`, `_flags.py`, `_provider_terms.py`, `_human_only_actions.py`, `_specs.py`, `_eval_suites.py` (their `abacus_tools.codegen` module or `make regenerate`), `backend/tests/durations.json`, workflow replay histories. Regenerate instead; resolve a conflict in one by regenerating, never by picking a side.
- **Applied migrations:** a file in `backend/migrations/versions/` that is already on `origin/main`. Add a new migration instead; keep one Alembic head. A migration that exists only on your branch can still be edited.

## Shell commands the hook refuses

Force pushes; `git commit --no-verify`; recursive deletion of root, home or the project; `sudo`; `chmod 777`; `terraform destroy`, `import` and `state`; `psql`, `pg_dump` and `pg_restore` against a non-local host; AWS production profiles; direct calls to model provider APIs (use `ai_gateway`); `alembic downgrade` against staging or production; `git checkout --ours/--theirs` on a generated file.

## Still binding, as rules rather than locks

The policy files keep their meaning and are changed deliberately, in the same change as the code that needs them: the permission matrix, the dependency allowlist, the glossary, the failure taxonomy, the coverage floor, evaluation suites, cost baselines and judge calibration, the provider terms register, and the human-only actions register (`docs/architecture/human-only-actions.yaml`, Q-02-T17: a change also needs a migration redefining `abacus_human_only_actions()`). Accepted ADRs are superseded by a new ADR rather than rewritten; `validate_docs` checks the supersede chain.
