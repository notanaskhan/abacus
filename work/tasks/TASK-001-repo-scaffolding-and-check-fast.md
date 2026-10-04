---
id: TASK-001
title: Repository scaffolding and make check-fast tooling
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: awaiting-plan-approval
branch: task-001-scaffolding
worktree:
created: 2026-10-04
updated: 2026-10-04
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Create the monorepo skeleton (ADR-010) and configure every tool behind `make check-fast` — formatting, linting, strict typing, import contracts, banned-pattern lints and document validation — so stage 1 runs and passes on the empty codebase (build plan §5.1 step 3, first half).

## Scope
**In**
- Directory skeleton per ADR-010 (empty packages only, no application code)
- Backend: `backend/pyproject.toml` (uv), `.python-version`, ruff (format + lint), pyright strict, import-linter contracts
- `backend/quality/banned_patterns.py` — extensible banned-pattern checker
- `backend/quality/validate_docs.py` — frontmatter and cross-reference validator for ADRs, specs, tasks
- Frontend: root `package.json` + `pnpm-workspace.yaml`; `apps/web` package, strict `tsconfig.json`, ESLint flat config with import-boundary rules, Prettier, minimal Vite + React entry
- Lockfiles: `backend/uv.lock`, `pnpm-lock.yaml` (so `make setup` with `--frozen-lockfile` works)
- `make check-fast` passes end to end; `Makefile` itself is **not** changed

**Out**
- Stage 2 (pytest suites, schema check, client drift, vitest) — TASK-002
- Secrets scan, dependency-allowlist enforcement, classification-tag lint — stage 1 per ADR-083 but not wired in the Makefile; TASK-002 unless Q1 says otherwise
- CI workflow YAML, Terraform, Docker / docker-compose
- Any application code: `app/main.py`, `worker/main.py`, models, routes (they arrive with SPEC-000 work)

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md` (§5 AC-20, §22)
- Build plan: `docs/product/build-plan.md` §5.1
- ADRs: ADR-009 (strict typing, `Any`/`type: ignore` rule), ADR-010 (layout, boundaries), ADR-083 (stage 1 contents), ADR-019 + ADR-057 (provider SDK / framework ban), ADR-014 (no raw connections), ADR-007/018 (unit of work)
- Reference: `Makefile` (`check-fast` target), `docs/architecture/dependency-allowlist.yaml`, `docs/architecture/protected-paths.md`, `.claude/hooks/_protected.py`

## Plan
- [ ] Plan approved by human (required for amber)
- [ ] Approval file `work/approvals/TASK-001.yaml` created by founder for the protected paths listed in step 0
- [ ] Blocking questions Q2 and Q3 answered

Steps:

0. [ ] **Protected-path approval (founder).** This task must create protected files. Requested paths:
   ```yaml
   task: TASK-001
   approved_by: founder
   expires: 2026-10-18
   paths:
     - backend/pyproject.toml
     - backend/uv.lock
     - backend/quality/*
     - package.json
     - pnpm-lock.yaml
     - apps/web/package.json
     - docs/architecture/dependency-allowlist.yaml   # only if Q4 approves new deps
   ```
   Record in this plan: *Approved by founder: paths …* (approval files are git-ignored).

1. [ ] **Directory skeleton** (ADR-010). Empty `__init__.py` everywhere; `.gitkeep` for empty dirs.
   ```
   backend/
     .python-version            3.12
     src/app/  src/worker/      __init__.py only (main.py comes with SPEC-000)
     src/modules/<m>/           __init__.py + empty api.py per module (list per Q3)
     src/<kernel>/              __init__.py — name per Q2 (`platform` collides with stdlib)
     src/ai_gateway/            __init__.py
     quality/                   __init__.py, banned_patterns.py, validate_docs.py
     migrations/                .gitkeep
     tests/{unit,integration,property,security,workflows}/   __init__.py; tests/conftest.py empty
   apps/web/{src,public}/
   packages/ui/  packages/api-client/  infra/  evals/       .gitkeep
   ```

2. [ ] **`backend/pyproject.toml`**
   - `[project]` name `abacus-backend`, `requires-python = ">=3.12"`, no runtime deps yet
   - `[dependency-groups] dev`: ruff, pyright, import-linter, pytest, pytest-asyncio, hypothesis, bandit (+ pyyaml, types-PyYAML per Q4)
   - `[build-system]` hatchling, packages = the five `src/` roots, so they import without `PYTHONPATH` hacks
   - `[tool.ruff]` py312, line-length 99, `src = ["src", "."]`; select `E F W I UP B SIM RUF ANN PGH T20 TID S`:
     - `T20` bans `print` (replaces the regex rule)
     - `PGH003` bans blanket `# type: ignore` (code required)
     - `ANN` + `ANN401` enforce typed signatures and flag `Any` in signatures
     - `TID251` banned-api: `anthropic`, `openai`, `langchain*`, `llama_index`, `crewai`, `autogen` (ADR-019, 057); `per-file-ignores` lifts `anthropic` for `src/ai_gateway/**` only
     - `S` (bandit rules via ruff); `S101` ignored under `tests/**`
   - `[tool.ruff.format]` defaults
   - `[tool.pyright]` `typeCheckingMode = "strict"`, `pythonVersion = "3.12"`, `include = ["src", "quality", "tests"]`, `venvPath = "."`, `venv = ".venv"`, `reportUnnecessaryTypeIgnoreComment = "error"`
   - `[tool.importlinter]` root packages = the five `src/` roots, contracts:
     1. **Top-level layers:** `app | worker` → `modules` → `ai_gateway` → `<kernel>` (lower may not import higher) — direction of `modules`↔`ai_gateway` to confirm, Q5
     2. **Module independence:** `modules.*` siblings independent, except through `api` (`ignore_imports` / allowed via banned_patterns rule below — import-linter cannot express "only `api`" directly)
     3. **In-module layering:** `routes → service → repository` per module, `containers` = every module. If import-linter rejects layers that don't exist yet, add this contract per module as each gains those files and note it in the `backend-module` skill (verify during step 7)

3. [ ] **`backend/quality/banned_patterns.py`** — `python -m quality.banned_patterns`, AST-based for Python where regex would false-positive, line regex otherwise. Rules are a module-level `list[Rule]` of frozen dataclasses (`id`, `description`, `adr`, `include` globs, `exclude` globs, checker). No inline suppression comments — exceptions only via `exclude` globs in this file (protected). Initial rules:
   | Rule | Enforces | Excluded |
   |---|---|---|
   | `session.commit()` / `session.flush()` / `session.rollback()` calls | Unit of work (ADR-007, 018) | `src/<kernel>/uow/**` |
   | `create_engine`, `create_async_engine`, `asyncpg.connect` | Tenant-scoped sessions only (ADR-014) | `src/<kernel>/db/**` |
   | `text()` / `.execute()` with f-string, `%`, `+` or `.format()` argument | Parameterised SQL | — |
   | Import of `modules.<b>.<x>` where `x != api`, from outside `modules/<b>/` | Module boundaries (ADR-010) | — |
   | `# type: ignore[...]` / `# pyright: ignore[...]` with no reason text after it | ADR-009 | — |
   | `Any` in code without an explanatory `#` comment on the line (imports exempt) | ADR-009 | — |
   Output `path:line: RULE-ID message (ADR-xxx)`; exit 0 clean, 1 on violations. Scans `src/`, `quality/`, `tests/`.

4. [ ] **`backend/quality/validate_docs.py`** — `python -m quality.validate_docs`, resolves repo root from its own location. Frontmatter must start at line 1; `_TEMPLATE.md` and `README.md` skipped.
   - **ADR** (`docs/adr/ADR-*.md`): id, title, status ∈ {proposed, accepted, deprecated, `superseded by ADR-NNN`}, date (ISO), deciders, risk_zone ∈ {green, amber, red}; id matches filename; ids unique; superseding ADR exists; every ADR appears in `docs/adr/README.md` index with matching status
   - **SPEC** (`docs/specs/SPEC-*.md`): id, title, status ∈ {draft, approved, in-progress, done, superseded}, owner, risk_zone, created, updated; id matches filename; every `related_adrs` / `related_specs` entry exists
   - **TASK** (`work/tasks/TASK-*.md`): id, title, spec, acceptance_criteria, risk_zone, status ∈ {todo, planning, awaiting-plan-approval, in-progress, blocked, in-review, done}, created, updated; id matches filename; `spec` exists; each AC id appears in that spec
   - Policy YAML (`permission-matrix.yaml`, `dependency-allowlist.yaml`) parses
   - Report every violation, then exit 1; exit 0 if clean

5. [ ] **Frontend tooling**
   - Root `package.json` (private, `packageManager: pnpm@<pinned>` via corepack, `engines.node >=20`), `pnpm-workspace.yaml` (`apps/*`, `packages/*`)
   - `apps/web/package.json`: `type: module`; scripts `dev`, `build`, `typecheck`, `lint`, `format`; deps react, react-dom; devDeps typescript, vite, eslint, prettier + Q4 packages
   - `tsconfig.json`: `strict`, `noUncheckedIndexedAccess`, `noEmit`, target/module ESNext, `moduleResolution: bundler`, `jsx: react-jsx`; includes `src` and `vite.config.ts`
   - `eslint.config.js` (flat, typescript-eslint strict-type-checked); boundary rules via core `no-restricted-imports` (no deep imports into `packages/*/src`, no `../../` across feature roots) — no import plugin needed
   - `.prettierrc` (`printWidth: 99`), `.prettierignore` (`dist`)
   - `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx` — minimal so `tsc` has input (TS18003 otherwise)

6. [ ] **Install and lock:** `make setup` (uv installs Python 3.12 itself; pnpm via corepack) producing `backend/uv.lock`, `pnpm-lock.yaml`

7. [ ] **Verify:** `make check-fast` exits 0. Then prove each gate bites: temporarily introduce one violation per gate (format, lint, pyright, import contract, each banned-pattern rule, a bad ADR frontmatter, TS strict error, ESLint, Prettier), confirm failure, revert. Record results in the progress log.

Files to create or change:
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version` *(first two protected)*
- `backend/quality/__init__.py`, `banned_patterns.py`, `validate_docs.py` *(protected)*
- `backend/src/**/__init__.py`, `backend/src/modules/*/api.py`, `backend/tests/**/__init__.py`, `backend/tests/conftest.py`
- `package.json`, `pnpm-lock.yaml` *(protected)*, `pnpm-workspace.yaml`
- `apps/web/package.json` *(protected)*, `tsconfig.json`, `eslint.config.js`, `.prettierrc`, `.prettierignore`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx`
- `.gitkeep` in `backend/migrations`, `apps/web/public`, `packages/ui`, `packages/api-client`, `infra`, `evals`
- `docs/architecture/dependency-allowlist.yaml` *(protected; only if Q4 approves)*

Tests to write (mapped to ACs) — written in a **separate session** (amber rule), run in stage 2:
- AC-20 → `backend/tests/unit/quality/test_banned_patterns.py`: `test_ac20_<rule>_flags_violation` and `test_ac20_<rule>_allows_clean_code` for every rule, plus exclude-glob behaviour
- AC-20 → `backend/tests/unit/quality/test_validate_docs.py`: missing field, bad enum, id/filename mismatch, dangling `related_adrs`, unknown AC, clean pack passes
- AC-20 → `make check-fast` exits 0 on the repo (step 7)

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation — n/a, no queries or endpoints
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals — n/a
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

Commands:
```
make setup
make check-fast
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| ruff, pyright, import-linter, pytest, pytest-asyncio, hypothesis, bandit | pinned in `uv.lock` | Stage 1/2 Python tooling | Allowlist (approved) |
| typescript, vite, eslint, prettier, react, react-dom | pinned in `pnpm-lock.yaml` | Frontend toolchain + entry | Allowlist (approved) |
| pyyaml, types-PyYAML (py dev) | latest | Parse frontmatter and policy YAML in `validate_docs` | **Pending — Q4** |
| typescript-eslint, @eslint/js, globals (ts dev) | latest | ESLint for TypeScript (flat config) | **Pending — Q4** |
| @vitejs/plugin-react (ts dev) | latest | Vite React/JSX transform | **Pending — Q4** |
| @types/react, @types/react-dom (ts dev) | latest | React types for strict `tsc` | **Pending — Q4** |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-04 21:10` — Task file created with plan. Awaiting founder approval.
- `2026-10-04 21:40` — Plan revised against build plan §5.1, ADR-009/010/083, protected paths and allowlist: added approval step, ruff-native rules, AST banned patterns, cross-reference doc checks, gate-bite verification, unlisted deps and blocking questions. No code written.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Line length 99 for both Python and Prettier | Consistent across languages | no |
| Banned patterns as a dataclass list in Python, not YAML | Co-located with checker; no extra parse step | no |
| validate_docs checks frontmatter and cross-references, not body | Frontmatter is the machine contract | no |
| Use ruff rules (T20, PGH, TID251, ANN) where they exist; custom checker only for the rest | Native rules are faster, editor-integrated and tested upstream | no |
| No inline suppression for banned patterns; exceptions only via exclude globs | `backend/quality/` is protected, so every exception gets founder review | no |
| No `main.py` stubs in `app/` and `worker/` | No application code in this task; SPEC-000 creates real entry points | no |
| Makefile unchanged | Its `check-fast` target already covers this task's gates | no |

## Gotchas and discoveries
- **`backend/src/platform/` shadows Python's stdlib `platform` module** once `src/` is importable — breaks pytest, uvicorn and others, or is silently shadowed by stdlib so `import platform.db` fails. ADR-010 mandates the name → Q2.
- The template files start with an HTML comment before `---`; real docs start frontmatter at line 1. `validate_docs` skips templates.
- The repo is not a git repository yet (frontmatter names a branch) → Q6.
- `.claude/settings.json` lives in `repo-docs-pack/`, but the session was opened in its parent `abacus/`, so the protection hooks are **not active** in that session. Open Claude Code in the repo root for hooks to load.
- Local toolchain: Python 3.9 system only (uv will fetch 3.12), Node 20.16, no pnpm (use corepack).
- `make check` will fail on empty test dirs (pytest exit 5 when nothing is collected) — TASK-002 concern.

## Questions for the human
- [ ] **Q1 — Stage 1 completeness.** ADR-083 stage 1 includes secrets scan, dependency allowlist and classification-tag lint; the Makefile `check-fast` target doesn't call them. Recommendation: separate TASK-002 with a Makefile approval, so this task changes no gate wiring.
- [ ] **Q2 — `platform` package name (blocking).** Options: (a) superseding ADR renaming `src/platform/` → `src/kernel/` ("shared kernel" is ADR-010's own wording), plus updates to `_protected.py`, `protected-paths.md` and AGENTS.md; (b) one namespace root `src/abacus/{app,worker,modules,platform,ai_gateway}`, which also changes Makefile targets (`abacus.app.main:app`). Recommendation: (a), smaller blast radius.
- [ ] **Q3 — Module list (blocking).** AGENTS.md lists twelve modules including `platform`; ADR-010 puts `platform` outside `modules/` and still says "the twelve modules". Is there a `modules/platform`, or are there eleven modules plus the kernel?
- [ ] **Q4 — New dependencies.** Approve and add to the allowlist: pyyaml, types-PyYAML (Python dev); typescript-eslint, @eslint/js, globals, @vitejs/plugin-react, @types/react, @types/react-dom (TS dev). Without pyyaml, `validate_docs` needs a hand-written restricted YAML parser (not recommended).
- [ ] **Q5 — Layer direction.** Confirm `app|worker → modules → ai_gateway → kernel`, i.e. `ai_gateway` never imports from `modules` (budgets, metering and prompt registry live in the gateway or the kernel).
- [ ] **Q6 — Repo root and git.** Confirm `repo-docs-pack/` is the repository root (the parent `abacus/` holds duplicate `AGENTS.md`, `SPEC-000` and a zip), and whether to `git init` there and create the `task-001-scaffolding` branch.
- [ ] **Q7 — Ruff rule set.** `E F W I UP B SIM RUF ANN PGH T20 TID S`. Additions or removals?

## Handoff
- **Current state:** Plan revised, not approved. No code written.
- **Exact next step:** Founder answers Q2–Q4 (blocking), creates `work/approvals/TASK-001.yaml` per step 0, ticks plan approval. Then start step 1.
- **Uncommitted or partial work:** None
- **Known failing checks:** N/A — no code yet
- **Open issues:** Q1–Q7
