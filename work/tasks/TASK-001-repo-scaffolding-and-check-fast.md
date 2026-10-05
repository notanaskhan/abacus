---
id: TASK-001
title: Repository scaffolding and make check-fast tooling
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-progress
branch: task-001-scaffolding
worktree:
created: 2026-10-04
updated: 2026-10-05
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Adopt the namespaced backend layout (ADR-101, superseding ADR-010's layout), move every protection and reference to it, then create the monorepo skeleton and configure every tool behind `make check-fast` — formatting, linting, strict typing, import contracts, banned-pattern lints and document validation — so stage 1 runs and passes on the empty codebase (build plan §5.1 step 3, first half).

## Scope
**In**
- ADR-101 *Namespaced backend package layout*; ADR-010 status → `superseded by ADR-101`; ADR index updated
- Reference updates for the new layout: `.claude/hooks/_protected.py` (**first**), `.github/CODEOWNERS`, `docs/architecture/protected-paths.md`, `AGENTS.md`, `Makefile` module paths, skills (`backend-module`, `ai-agent`), `SPEC-000`, glossary *Kernel* entry
- Directory skeleton per ADR-101 (empty packages only, no application code)
- Backend: `backend/pyproject.toml` (uv), `.python-version`, ruff (format + lint), pyright strict, import-linter contracts
- `abacus_tools.quality.banned_patterns` — extensible banned-pattern checker
- `abacus_tools.quality.validate_docs` — frontmatter and cross-reference validator for ADRs, specs, tasks
- Frontend: root `package.json` + `pnpm-workspace.yaml`; `apps/web` package, strict `tsconfig.json`, ESLint flat config with import-boundary rules, Prettier, minimal Vite + React entry
- Lockfiles: `backend/uv.lock`, `pnpm-lock.yaml` (so `make setup` with `--frozen-lockfile` works)
- Allowlist entries for the six Q4-approved packages
- `make check-fast` passes end to end. The `Makefile` changes **only** in module paths (Q2); no gate is added, removed or rewired

**Out**
- Stage 2 (pytest suites, schema check, client drift, vitest) — TASK-002
- Secrets scan, dependency-allowlist enforcement, classification-tag lint — **TASK-002**, which runs immediately after this task and before any SPEC-000 work (Q1)
- CI workflow YAML, Terraform, Docker / docker-compose
- Any application code: `abacus/api/main.py`, `abacus/worker/main.py`, models, routes (they arrive with SPEC-000 work)
- Editing accepted ADRs other than ADR-010's status line (ADR-047 and ADR-082 path references are remapped by ADR-101, not edited)

## Context to load
- Spec: `docs/specs/SPEC-000-walking-skeleton.md` (§5 AC-20, §10, §22)
- Build plan: `docs/product/build-plan.md` §5.1
- ADRs: ADR-008 (twelve modules), ADR-009 (strict typing, `Any`/`type: ignore` rule), ADR-010 (layout being superseded, boundaries), ADR-083 (stage 1 contents), ADR-019 + ADR-057 (provider SDK / framework ban), ADR-014 (no raw connections), ADR-007/018 (unit of work), ADR-047 + ADR-082 (agent spec paths), ADR-085 (synthetic data)
- Reference: `Makefile`, `docs/architecture/dependency-allowlist.yaml`, `docs/architecture/protected-paths.md`, `.claude/hooks/_protected.py`, `.github/CODEOWNERS`

## Plan
- [x] Plan approved by human (founder, 2026-10-05: "agreed, proceed")
- [x] Approval file `work/approvals/TASK-001.yaml` created **by the agent at the founder's explicit instruction** (2026-10-05: "i dont want to create by hand, create the approval file and proceed")
- Approved by founder: paths listed under *Approval file text*, expires 2026-10-18
- [x] Blocking questions Q2, Q3, Q4 answered (2026-10-04)
- [x] Q5, Q8, Q9 confirmed as recommended (2026-10-05)

Target layout (ADR-101):
```
backend/src/
  abacus/                      the product — the only package in the runtime wheel
    api/                       HTTP entry point (was app/)
    worker/                    Temporal worker entry point
    kernel/                    shared kernel: db sessions, tenant context, uow, outbox, crypto, config, logging
    modules/<twelve modules>/  identity · organisations · engagements · requests · evidence · connections ·
                               ledger · sampling · agents · audit_trail · communications · platform
    ai_gateway/
  abacus_tools/                dev and ops tooling — never imported by abacus, not in the runtime wheel (Q8)
    quality/                   banned_patterns, validate_docs, schema_check (was backend/quality/)
    synthetic/                 seeded synthetic generator (ADR-085)
    loadtest/                  load profiles (ADR-075)
```
`abacus.kernel` is not a module. `abacus.modules.platform` is the twelfth domain module (tenant settings, feature flags, usage metering) and AGENTS.md's twelve-module list stands (Q3).

Steps:

0. [x] **Protected-path approval (founder).** Every path below matches a hook pattern (`_protected.py` `PROTECTED` / `PROTECTED_IF_EXISTS`); the exact text is under *Approval file text*. Record in this plan: *Approved by founder: paths …* (approval files are git-ignored).

1. [x] **Branch** `task-001-scaffolding` from `main`; commit this task-file revision first.

2. [x] **Hook protected-path list — before any code exists under the new layout.** Edit `.claude/hooks/_protected.py`:
   - `backend/quality/*` → `backend/src/abacus_tools/quality/*`, `backend/src/abacus_tools/quality/**/*`
   - `backend/src/modules/identity/authz/…` → `backend/src/abacus/modules/identity/authz/…`
   - `backend/src/platform/{db,uow,crypto}/…` → `backend/src/abacus/kernel/{db,uow,crypto}/…`
   - `backend/src/modules/audit_trail/…` → `backend/src/abacus/modules/audit_trail/…`
   - docstring example path → `backend/src/abacus/kernel/uow/**/*`
   - `ai_gateway` stays hook-unprotected (CODEOWNERS only) as today — see Q9

   Then prove it, without the approval file covering the targets: `Write` to `backend/src/abacus/kernel/uow/x.py`, `backend/src/abacus/kernel/db/x.py`, `backend/src/abacus/modules/audit_trail/x.py`, `backend/src/abacus_tools/quality/x.py` and a shell `> backend/src/abacus/kernel/crypto/x.py` must all be **blocked**. Record results in the progress log.

3. [x] **Server-side and policy mirrors**
   - `.github/CODEOWNERS`: `/backend/quality/` → `/backend/src/abacus_tools/quality/`; `/backend/src/{modules/identity/authz,platform/db,platform/uow,platform/crypto,modules/audit_trail,ai_gateway}/` → their `/backend/src/abacus/…` equivalents
   - `docs/architecture/protected-paths.md`: `backend/quality/` → `backend/src/abacus_tools/quality/`; example approval path; "Red-zone code" bullet names `abacus.kernel` db / uow / crypto

4. [x] **ADR-101** `docs/adr/ADR-101-namespaced-backend-layout.md` (new file, `status: accepted`, `deciders: Founder`, `risk_zone: amber`) stating:
   - **Context:** `src/platform` shadows stdlib `platform`; flat top-level names (`app`, `worker`, `quality`, `synthetic`, `loadtest`, `tests`) can collide with stdlib or third-party distributions; "platform" named both the shared kernel and the twelfth module
   - **Decision:** all product code under one root package `abacus` (layout above); tooling under `abacus_tools`; no other top-level importable name under `backend/src/`; `abacus` never imports `abacus_tools`
   - **Kernel vs platform, explicitly:** the shared kernel (database sessions, tenant context, unit of work, outbox, encryption, config, logging) is `abacus.kernel` — not a module, not one of the twelve; `abacus.modules.platform` is the twelfth domain module (tenant settings, feature flags, usage metering), consistent with ADR-008 and AGENTS.md
   - **Path remapping** for accepted ADRs that cannot be edited: ADR-010 `src/app` → `src/abacus/api`, `src/worker` → `src/abacus/worker`, `src/modules` → `src/abacus/modules`, `src/platform` → `src/abacus/kernel`, `src/ai_gateway` → `src/abacus/ai_gateway`; ADR-047 and ADR-082 `backend/src/agents/` → `backend/src/abacus/modules/agents/`, `backend/src/ai_gateway/` → `backend/src/abacus/ai_gateway/`; ADR-044/085 `synthetic.*` examples → `abacus_tools.synthetic.*`
   - **Options:** (A) namespaced root — chosen; (B) rename only `platform` → `kernel` — rejected, leaves other collision-prone top-level names; (C) keep flat layout with `PYTHONPATH` ordering — rejected, fragile
   - **Enforcement:** hatch wheel packages only `src/abacus`; import-linter layers + `abacus ↛ abacus_tools` contract; banned-pattern `LAYOUT-001` (only `abacus/`, `abacus_tools/` under `backend/src/`); hook, CODEOWNERS and protected-paths.md list `abacus` paths
   - Everything else in ADR-010 (monorepo, uv/pnpm, Makefile as sole command surface, boundary tools) carries forward unchanged
   - Then: ADR-010 frontmatter `status: superseded by ADR-101` (only edit); `docs/adr/README.md` ADR-010 row status → `superseded by ADR-101`, new ADR-101 row

5. [x] **Glossary** `docs/product/glossary.md`, *Agents and platform* section: `| Kernel | The shared technical foundation every module uses: database sessions, tenant context, unit of work, outbox, encryption, config, logging. Not a module. | abacus.kernel | platform (that is the twelfth module), core, common, shared, utils |`

6. [x] **AGENTS.md** module map: path → `backend/src/abacus/modules/`, twelve modules unchanged; add one line: *Shared kernel (`abacus.kernel`) is not a module; modules use it, it never imports modules. Tooling lives in `abacus_tools` and is never imported by `abacus`. (ADR-101)*

7. [x] **Makefile** — module paths only, gates unchanged:
   `app.main:app` → `abacus.api.main:app`; `worker.main` → `abacus.worker.main`; `quality.banned_patterns|validate_docs|schema_check` → `abacus_tools.quality.…`; `app.export_openapi` → `abacus.api.export_openapi`; `loadtest.run` → `abacus_tools.loadtest.run`; `synthetic.seed` → `abacus_tools.synthetic.seed`

8. [x] **Skills and spec**
   - `.claude/skills/backend-module/SKILL.md`: `backend/src/modules/<name>/` → `backend/src/abacus/modules/<name>/`; note kernel imports (`from abacus.kernel.uow import …`)
   - `.claude/skills/ai-agent/SKILL.md`: `backend/src/agents/specs/<id>.yaml` → `backend/src/abacus/modules/agents/specs/<id>.yaml`
   - `docs/specs/SPEC-000-walking-skeleton.md` §10: same spec path; add `ADR-101` to `related_adrs`; bump `updated`

9. [x] **Directory skeleton** (ADR-101). Empty `__init__.py` everywhere; `.gitkeep` for empty dirs.
   ```
   backend/
     .python-version                      3.12
     src/abacus/__init__.py  py.typed
     src/abacus/{api,worker,kernel,ai_gateway}/__init__.py      (main.py comes with SPEC-000)
     src/abacus/modules/__init__.py
     src/abacus/modules/<12>/__init__.py + empty api.py
     src/abacus_tools/__init__.py
     src/abacus_tools/quality/__init__.py, banned_patterns.py, validate_docs.py
     src/abacus_tools/{synthetic,loadtest}/__init__.py
     migrations/                          .gitkeep
     tests/{unit,integration,property,security,workflows}/.gitkeep; tests/conftest.py empty
   apps/web/{src,public}/
   packages/ui/  packages/api-client/  infra/  evals/       .gitkeep
   ```
   `tests/` has no `__init__.py`; pytest runs with `--import-mode=importlib` so `tests` is never a top-level importable name (pytest config lands in TASK-002; recorded here for consistency).

10. [x] **`backend/pyproject.toml`**
    - `[project]` name `abacus-backend`, `requires-python = ">=3.12"`, no runtime deps yet
    - `[dependency-groups] dev`: ruff, pyright, import-linter, pytest, pytest-asyncio, hypothesis, bandit, pyyaml, types-PyYAML
    - `[build-system]` hatchling; `[tool.hatch.build.targets.wheel] packages = ["src/abacus"]`; dev install exposes `src/` so `abacus_tools` imports locally without `PYTHONPATH` hacks (verify in step 14)
    - `[tool.ruff]` py312, line-length 99, `src = ["src"]`, isort `known-first-party = ["abacus", "abacus_tools"]`; select `E F W I UP B SIM RUF ANN PGH T20 TID S`:
      - `T20` bans `print` (`abacus_tools/**` exempt — CLIs print reports)
      - `PGH003` bans blanket `# type: ignore` (code required)
      - `ANN` + `ANN401` enforce typed signatures and flag `Any` in signatures
      - `TID251` banned-api: `anthropic`, `openai`, `langchain*`, `llama_index`, `crewai`, `autogen`, `abacus_tools` (ADR-019, 057, 101); `per-file-ignores` lifts `anthropic` for `src/abacus/ai_gateway/**` only
      - `S` (bandit rules via ruff); `S101` ignored under `tests/**`
    - `[tool.ruff.format]` defaults
    - `[tool.pyright]` `typeCheckingMode = "strict"`, `pythonVersion = "3.12"`, `include = ["src", "tests"]`, `venvPath = "."`, `venv = ".venv"`, `reportUnnecessaryTypeIgnoreComment = "error"`
    - `[tool.importlinter]` `root_packages = ["abacus", "abacus_tools"]`, contracts:
      1. **Top-level layers:** `abacus.api | abacus.worker` → `abacus.modules` → `abacus.ai_gateway` → `abacus.kernel` (Q5 still open on `modules`↔`ai_gateway`)
      2. **Product never imports tooling:** forbidden `abacus` → `abacus_tools`
      3. **Module boundaries:** only-`api` cross-module imports enforced by banned-pattern `BOUND-001` (import-linter cannot express "only `api`" directly)
      4. **In-module layering:** `routes → service → repository` per module, `containers` = every `abacus.modules.*`. If import-linter rejects layers that don't exist yet, add per module as each gains those files and note it in the `backend-module` skill (verify in step 14)

11. [x] **`abacus_tools/quality/banned_patterns.py`** — `python -m abacus_tools.quality.banned_patterns`, AST-based for Python where regex would false-positive, line regex otherwise. Rules are a module-level `list[Rule]` of frozen dataclasses (`id`, `description`, `adr`, `include` globs, `exclude` globs, checker). No inline suppression comments — exceptions only via `exclude` globs in this file (protected). Initial rules:
    | Rule | Enforces | Excluded |
    |---|---|---|
    | `session.commit()` / `session.flush()` / `session.rollback()` calls | Unit of work (ADR-007, 018) | `src/abacus/kernel/uow/**` |
    | `create_engine`, `create_async_engine`, `asyncpg.connect` | Tenant-scoped sessions only (ADR-014) | `src/abacus/kernel/db/**` |
    | `text()` / `.execute()` with f-string, `%`, `+` or `.format()` argument | Parameterised SQL | — |
    | `BOUND-001` import of `abacus.modules.<b>.<x>` where `x != api`, from outside `abacus/modules/<b>/` | Module boundaries (ADR-008, 101) | — |
    | `LAYOUT-001` any entry under `backend/src/` other than `abacus/`, `abacus_tools/` | Namespaced layout (ADR-101) | — |
    | `# type: ignore[...]` / `# pyright: ignore[...]` with no reason text after it | ADR-009 | — |
    | `Any` in code without an explanatory `#` comment on the line (imports exempt) | ADR-009 | — |
    Output `path:line: RULE-ID message (ADR-xxx)`; exit 0 clean, 1 on violations. Scans `src/`, `tests/`.

12. [x] **`abacus_tools/quality/validate_docs.py`** — `python -m abacus_tools.quality.validate_docs`, resolves repo root from its own location. Frontmatter must start at line 1; `_TEMPLATE.md` and `README.md` skipped.
    - **ADR** (`docs/adr/ADR-*.md`): id, title, status ∈ {proposed, accepted, deprecated, `superseded by ADR-NNN`}, date (ISO), deciders, risk_zone ∈ {green, amber, red}; id matches filename; ids unique; superseding ADR exists; every ADR appears in `docs/adr/README.md` index with matching status
    - **SPEC** (`docs/specs/SPEC-*.md`): id, title, status ∈ {draft, approved, in-progress, done, superseded}, owner, risk_zone, created, updated; id matches filename; every `related_adrs` / `related_specs` entry exists
    - **TASK** (`work/tasks/TASK-*.md`): id, title, spec, acceptance_criteria, risk_zone, status ∈ {todo, planning, awaiting-plan-approval, in-progress, blocked, in-review, done}, created, updated; id matches filename; `spec` exists; each AC id appears in that spec
    - Policy YAML (`permission-matrix.yaml`, `dependency-allowlist.yaml`) parses
    - Report every violation, then exit 1; exit 0 if clean

13. [x] **Frontend tooling**
    - Root `package.json` (private, `packageManager: pnpm@<pinned>` via corepack, `engines.node >=20`), `pnpm-workspace.yaml` (`apps/*`, `packages/*`)
    - `apps/web/package.json`: `type: module`; scripts `dev`, `build`, `typecheck`, `lint`, `format`; deps react, react-dom; devDeps typescript, vite, eslint, prettier, typescript-eslint, @vitejs/plugin-react, @types/react, @types/react-dom
    - `tsconfig.json`: `strict`, `noUncheckedIndexedAccess`, `noEmit`, target/module ESNext, `moduleResolution: bundler`, `jsx: react-jsx`; includes `src` and `vite.config.ts`
    - `eslint.config.js` (flat, `tseslint.config(...)` with typescript-eslint `strictTypeChecked`; `disableTypeChecked` for `*.js`). **No `@eslint/js`, no `globals`** (not approved — Q4): typescript-eslint ships its own `eslint-recommended` overrides and `no-undef` is off for TypeScript, so neither is required. Boundary rules via core `no-restricted-imports` (no deep imports into `packages/*/src`, no `../../` across feature roots)
    - `.prettierrc` (`printWidth: 99`), `.prettierignore` (`dist`)
    - `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx` — minimal so `tsc` has input (TS18003 otherwise)
    - `docs/architecture/dependency-allowlist.yaml` entries (approved 2026-10-04, Q4):
      ```yaml
      # python.dev
      pyyaml: approved            # parse doc frontmatter and policy YAML in abacus_tools.quality.validate_docs
      types-PyYAML: approved      # pyyaml stubs; required for strict Pyright (ADR-009)
      # typescript.dev
      typescript-eslint: approved       # ESLint parser and rules for TypeScript (ADR-009, 010)
      "@vitejs/plugin-react": approved  # Vite React/JSX transform (ADR-011)
      "@types/react": approved          # React types for strict tsc (ADR-009)
      "@types/react-dom": approved      # React DOM types for strict tsc (ADR-009)
      ```

14. [x] **Install and lock:** `make setup` (uv installs Python 3.12 itself; pnpm via corepack) producing `backend/uv.lock`, `pnpm-lock.yaml`. If any further package turns out to be needed: **stop and ask** (Q4).

15. [x] **Verify:** `make check-fast` exits 0. Then deliberately break each gate to prove it fails: one violation per gate (format, lint, pyright, each import-linter contract incl. `abacus → abacus_tools`, each banned-pattern rule incl. `LAYOUT-001` with a stray `backend/src/platform/`, a bad ADR frontmatter, ADR index status mismatch, TS strict error, ESLint, Prettier), confirm failure, revert. Record results in the progress log.

### Approval file text
`work/approvals/TASK-001.yaml` — every hook-protected path this task touches, exact files where known:
```yaml
task: TASK-001
approved_by: founder
expires: 2026-10-18
paths:
  # step 2 — hook list (first)
  - .claude/hooks/_protected.py
  # step 3 — server-side and policy mirrors
  - .github/CODEOWNERS
  - docs/architecture/protected-paths.md
  # step 4 — supersede ADR-010 (status line only)
  - docs/adr/ADR-010-monorepo.md
  # steps 5–8 — references
  - docs/product/glossary.md
  - AGENTS.md
  - Makefile
  - .claude/skills/backend-module/SKILL.md
  - .claude/skills/ai-agent/SKILL.md
  # step 9 — audit_trail skeleton (red-zone module path)
  - backend/src/abacus/modules/audit_trail/__init__.py
  - backend/src/abacus/modules/audit_trail/api.py
  # steps 10–14 — tooling, manifests, lockfiles, allowlist
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/src/abacus_tools/quality/*
  - package.json
  - pnpm-lock.yaml
  - apps/web/package.json
  - docs/architecture/dependency-allowlist.yaml
reason: TASK-001 — ADR-101 namespaced layout, protection moves, scaffolding, check-fast tooling, Q4 deps
```
Deliberately **not** listed: `backend/src/abacus/kernel/{db,uow,crypto}/**` and `backend/src/abacus/modules/identity/authz/**` (nothing is created there — they stay blocked, which step 2 relies on), `CLAUDE.md`. Not hook-protected but CODEOWNERS-reviewed in the PR: `docs/adr/ADR-101-…md`, `docs/adr/README.md`.

### Files changed (filled in as each step lands)
| Step | File | Change |
|---|---|---|
| — | `work/tasks/TASK-001-repo-scaffolding-and-check-fast.md` | Plan revised; approvals and progress recorded |
| — | `work/approvals/TASK-001.yaml` (git-ignored) | Created by agent on founder instruction |
| 2 | `.claude/hooks/_protected.py` | Paths moved to `abacus` layout; `from __future__ import annotations` (Python 3.9 crash fix) |
| 3 | `.github/CODEOWNERS` | Paths moved to `abacus` layout |
| 3 | `docs/architecture/protected-paths.md` | Paths moved; red-zone bullet names kernel packages |
| 4 | `docs/adr/ADR-101-namespaced-backend-layout.md` | New |
| 4 | `docs/adr/ADR-010-monorepo.md` | `status: superseded by ADR-101` only |
| 4 | `docs/adr/README.md` | ADR-010 status; ADR-101 row |
| 5 | `docs/product/glossary.md` | *Kernel* entry |
| 6 | `AGENTS.md` | Module map path; kernel / tooling line |
| 7 | `Makefile` | Module paths only |
| 8 | `.claude/skills/backend-module/SKILL.md` | Layout path; kernel import rule |
| 8 | `.claude/skills/ai-agent/SKILL.md` | Agent spec path |
| 8 | `docs/specs/SPEC-000-walking-skeleton.md` | Agent spec path; `ADR-101` in `related_adrs`; `updated` |
| 9 | `backend/.python-version`, `backend/src/abacus/**/__init__.py`, `py.typed`, `modules/*/api.py`, `backend/src/abacus_tools/{,synthetic/,loadtest/}__init__.py`, `backend/migrations/.gitkeep`, `backend/tests/*/.gitkeep`, `backend/tests/conftest.py`, `apps/web/public/.gitkeep`, `packages/{ui,api-client}/.gitkeep`, `evals/.gitkeep` | New skeleton |
| 10 | `backend/pyproject.toml`, `backend/uv.lock` | New |
| 11 | `backend/src/abacus_tools/quality/{__init__,banned_patterns}.py` | New |
| 12 | `backend/src/abacus_tools/quality/validate_docs.py` | New |
| 13 | `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `apps/web/{package.json,tsconfig.json,eslint.config.js,.prettierrc,.prettierignore,vite.config.ts,index.html,src/main.tsx,src/App.tsx}` | New |
| 13 | `docs/architecture/dependency-allowlist.yaml` | Six Q4 packages added |
| Q10 | `docs/adr/ADR-024-need-to-know-metadata-vs-content.md`, `docs/adr/ADR-058-agent-hierarchy.md` | `title:` quoted; no other change |

Tests to write (mapped to ACs) — written in a **separate session** (amber rule), run in stage 2:
- AC-20 → `backend/tests/unit/quality/test_banned_patterns.py`: `test_ac20_<rule>_flags_violation` and `test_ac20_<rule>_allows_clean_code` for every rule, plus exclude-glob behaviour
- AC-20 → `backend/tests/unit/quality/test_validate_docs.py`: missing field, bad enum, id/filename mismatch, dangling `related_adrs`, unknown AC, superseded-by target missing, index status mismatch, clean pack passes
- AC-20 → `make check-fast` exits 0 on the repo (step 15)

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed — scan itself arrives in TASK-002 (Q1)
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation — n/a, no queries or endpoints
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals — n/a
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed (ADR-101)
- [ ] No reference to `backend/src/{app,worker,platform,modules,ai_gateway}` or `backend/quality` remains outside ADR-010 and this task file (`grep` in step 15)

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
| pyyaml, types-PyYAML (py dev) | pinned in `uv.lock` | Parse frontmatter and policy YAML; stubs for strict Pyright | Founder, 2026-10-04 (Q4) |
| typescript-eslint (ts dev) | pinned in `pnpm-lock.yaml` | ESLint for TypeScript (flat config) | Founder, 2026-10-04 (Q4) |
| @vitejs/plugin-react (ts dev) | pinned in `pnpm-lock.yaml` | Vite React/JSX transform | Founder, 2026-10-04 (Q4) |
| @types/react, @types/react-dom (ts dev) | pinned in `pnpm-lock.yaml` | React types for strict `tsc` | Founder, 2026-10-04 (Q4) |
| ~~@eslint/js, globals~~ | — | Dropped: not approved and not required | — |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-04 21:10` — Task file created with plan. Awaiting founder approval.
- `2026-10-04 21:40` — Plan revised against build plan §5.1, ADR-009/010/083, protected paths and allowlist: added approval step, ruff-native rules, AST banned patterns, cross-reference doc checks, gate-bite verification, unlisted deps and blocking questions. No code written.
- `2026-10-04 22:30` — Environment fixed (Q6): `git init` in `repo-docs-pack/`, initial commit `48ae9a3`, pushed to private `github.com/notanaskhan/abacus`; CODEOWNERS set to @notanaskhan @ayushkbhatia (`a98490f`). Branch protection deferred by founder. Bot clone created at `~/Downloads/abacus/abacus-bot` (identity `abacus-bot`, founder credentials isolated); bot GitHub account deferred. No code written.
- `2026-10-04` — Founder answered Q1–Q4 and Q7, confirmed hooks load from the repo root (Q6). Plan revised: ADR-101 namespaced layout (`abacus`, `abacus_tools`), hook list moved first (step 2) with block tests, reference-update steps 3–8, Q4 deps (six, `@eslint/js` and `globals` dropped), approval file text expanded. Files changed: this task file only. No code written. Stopped for final approval.
- `2026-10-05` — Founder approved the plan and Q5/Q8/Q9 recommendations. Hook probe: a `Write` to protected `backend/quality/hook_probe.py` was **not blocked** — project hooks are not loaded in this session (it was started from `~/Downloads/abacus/`, not the repo root). Probe file and empty `backend/` removed. Created branch `task-001-scaffolding`, committed this task file. Stopped before step 2: hooks inactive and approval file `work/approvals/TASK-001.yaml` not yet created.
- `2026-10-05` — Founder instructed the agent to create the approval file and proceed. Steps 1–13 done.
  - **Hook bug found and fixed (step 2):** `_protected.py` used `str | None`, which raises `TypeError` on the system `python3` (3.9.6). Every hook therefore exited 1 — a *non-blocking* error in Claude Code — so **no protection has ever been enforced locally**. This, not the session directory, is why the 2026-10-05 probe write went through. Fixed with `from __future__ import annotations`.
  - Step 2 block tests (hook run directly with `CLAUDE_PROJECT_DIR` set): BLOCKED kernel/{uow,db,crypto}, identity/authz, audit_trail/x.py, CLAUDE.md, work/approvals/x.yaml, shell `>` into kernel/crypto, `uv add`; ALLOWED approved paths (audit_trail/api.py, abacus_tools/quality/*) and unprotected ones.
  - `infra/.gitkeep` created then removed: `infra/*` is protected and was not in the approval; `infra/` arrives with Terraform.
  - Step 15 gate-break, each confirmed failing then reverted: ruff format, ruff T201, ruff TID251 (`anthropic` outside gateway fails; inside `abacus.ai_gateway` passes), pyright, import-linter ×3 (kernel→modules, abacus→abacus_tools, repository→service), banned patterns UOW-001, DB-001, SQL-001, BOUND-001, TYPE-001, ANY-001, LAYOUT-001 (stray `src/platform/`), validate_docs (bad status/zone/date/id, missing index row, dangling superseded-by, index status mismatch), tsc, ESLint (floating promise; deep import into `packages/*/src`), Prettier.
  - Gate-break caught a validator bug: an impossible date (`2026-13-01`) crashed `validate_docs` (PyYAML raises `ValueError`). Fixed and re-verified.
  - `make check-fast` result: every gate passes **except** `validate_docs`, which correctly reports invalid YAML frontmatter in accepted ADR-024 and ADR-058 (unquoted `:` in `title`). Not fixed: accepted ADRs are protected and not in the approval — Q10.
  - Frontend installed with Node 25.9 via `npx pnpm@12.9.1` (lockfile is Node-version-independent). `make check-fast` was run with a temporary `pnpm` shim in the session scratchpad — Q11.

- `2026-10-05` — Q10 and Q11 approved. Appended ADR-024 and ADR-058 to the approval file and quoted their titles. Installed Node 24.21.0 (Homebrew `node@24`), `corepack enable` → pnpm 12.9.1. With Node 24 first on `PATH`: `make setup` exit 0 (frozen lockfile, no lock changes), **`make check-fast` exit 0**. Remaining: AC-20 tests from a separate session, then PR.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Line length 99 for both Python and Prettier | Consistent across languages | no |
| Banned patterns as a dataclass list in Python, not YAML | Co-located with checker; no extra parse step | no |
| validate_docs checks frontmatter and cross-references, not body | Frontmatter is the machine contract | no |
| Use ruff rules (T20, PGH, TID251, ANN) where they exist; custom checker only for the rest | Native rules are faster, editor-integrated and tested upstream (endorsed by founder, Q7) | no |
| No inline suppression for banned patterns; exceptions only via exclude globs | `abacus_tools/quality/` is protected, so every exception gets founder review | no |
| No `main.py` stubs in `abacus/api` and `abacus/worker` | No application code in this task; SPEC-000 creates real entry points | no |
| All backend product code under `abacus` (`api`, `worker`, `kernel`, `modules`, `ai_gateway`) | No top-level name can collide with stdlib or third-party packages (Q2) | **yes — ADR-101** |
| Shared kernel is `abacus.kernel`; `platform` remains the twelfth module | Two concepts shared one name (Q3) | **yes — ADR-101** + glossary |
| Tooling under a second root `abacus_tools`, not `abacus.tooling` | Kept out of the runtime wheel; one forbidden contract keeps product code from importing it (Q8) | ADR-101 |
| `tests/` without `__init__.py`, pytest `--import-mode=importlib` | Keeps `tests` from becoming a top-level importable name | no |
| Hook list updated before any code under the new layout | Protections must exist before the paths they protect (founder instruction) | no |
| Gate-break verification kept | Proves each gate fails on a violation (endorsed by founder) | no |
| Makefile changes limited to module paths | Gates and wiring unchanged; TASK-002 owns new gates | no |
| No ruff `TID251` ban on `abacus_tools` (plan said ruff + import-linter) | Ruff can't lift a single banned API per path; banning it would also flag `abacus_tools` and tests importing it. import-linter's forbidden contract is the enforcer | no |
| `TID251` lifted wholesale in `src/abacus/ai_gateway/**` | Ruff per-file-ignores work per rule, not per banned module; matches ADR-019/057 ("outside ai_gateway") | no |
| `T20` (print) lifted in `src/abacus_tools/**` | Checkers are CLIs that print reports | no |
| In-module layers marked optional `(routes)` etc. | import-linter accepts containers whose layers don't exist yet; no per-module contract churn | no |
| `engines.node >=22.12`, pnpm 12.9.1 (was `>=20`) | Node 20 is EOL (Apr 2026); Vite 8, ESLint 10 and plugin-react 6 need ≥20.19 | no |
| TypeScript `~5.9.3`, not 7.x | typescript-eslint 8.71 peer range is `>=4.8.4 <6.1.0` | no |
| ESLint config via `defineConfig` from `eslint/config` | `tseslint.config()` is deprecated in typescript-eslint 8 | no |

## Gotchas and discoveries
- **`backend/src/platform/` shadowed Python's stdlib `platform`** — resolved by ADR-101 (namespaced root).
- The template files start with an HTML comment before `---`; real docs start frontmatter at line 1. `validate_docs` skips templates.
- Branch protection is **off**, so CODEOWNERS is not enforced server-side yet — this task edits CODEOWNERS and the hook in the same PR, so founder review of that PR is the only check.
- Bot clone `~/Downloads/abacus/abacus-bot` has no GitHub credentials until the bot account exists — it cannot push or pull.
- Cursor sets `GIT_ASKPASS`; credential-less git commands in the bot clone pop a Cursor sign-in prompt instead of failing. Never enter founder credentials there.
- `~/Downloads/abacus/` (outside the repo) still holds loose copies of `AGENTS.md` and `SPEC-000-walking-skeleton.md`; they will go stale after steps 6 and 8. Delete or ignore them; open Claude Code only in `repo-docs-pack/`.
- `guard_bash.py` blocks shell writes by matching protected-path stems; after step 2 the stems become `backend/src/abacus/kernel/db` etc., so old stems stop being guarded — intended, since nothing may exist at the old paths (`LAYOUT-001`).
- `ai_gateway` is in CODEOWNERS but not in the hook list (pre-existing) — Q9.
- ADR-047 and ADR-082 reference `backend/src/agents/`, which matched neither layout; ADR-101 maps it to `abacus/modules/agents/`.
- Local toolchain: Python 3.9 system only (uv will fetch 3.12), Node 20.16, no pnpm (use corepack).
- `make check` will fail on empty test dirs (pytest exit 5 when nothing is collected) — TASK-002 concern.
- **Hooks were never enforcing** before 2026-10-05: `_protected.py` crashed on Python 3.9 and Claude Code treats hook exit 1 as non-blocking. Any earlier "hook passed" observation is void. TASK-002 should add a hook self-test to `make check-fast` so a crashing hook fails loudly.
- `/opt/homebrew/opt/node@24` is a symlink to Node 25 (non-LTS, no bundled corepack); `/usr/local/bin/node` is 20.16 (EOL) and root-owned, so `corepack enable` cannot write there.

## Questions for the human
- [x] **Q1 — Stage 1 completeness.** Answered 2026-10-04: secrets scan, allowlist enforcement (and classification-tag lint) go to TASK-002, which runs immediately after this task and before any SPEC-000 work.
- [x] **Q2 — `platform` package name.** Answered 2026-10-04: single namespaced root `backend/src/abacus/{api,worker,kernel,modules,ai_gateway}`; ADR-101 supersedes ADR-010's layout; hook list updated first; every reference updated.
- [x] **Q3 — Module list.** Answered 2026-10-04: kernel is `abacus.kernel`, not a module; `platform` stays the twelfth module at `abacus.modules.platform`; AGENTS.md is correct; stated in ADR-101 and the glossary.
- [x] **Q4 — New dependencies.** Answered 2026-10-04: approved pyyaml, types-PyYAML, typescript-eslint, @vitejs/plugin-react, @types/react, @types/react-dom — nothing else. `@eslint/js` and `globals` dropped from the plan.
- [x] **Q5 — Layer direction.** Confirmed 2026-10-05 as recommended. Proposed `abacus.api|abacus.worker → abacus.modules → abacus.ai_gateway → abacus.kernel`. **Recommendation:** confirm — `ai_gateway` never imports from `modules`; budgets, metering and prompt registry live in the gateway or the kernel, and modules call the gateway. (Note: usage metering is listed under `modules.platform`; the gateway would *write* usage through the kernel or emit events, never import `modules.platform`.)
- [x] **Q6 — Repo root and git.** Resolved 2026-10-04: `repo-docs-pack/` is the root; hooks confirmed loaded via `/hooks`.
- [x] **Q7 — Ruff rule set.** Answered 2026-10-04: Ruff-first approach endorsed; rule set as listed.
- [x] **Q8 — Tooling location.** Confirmed 2026-10-05: `abacus_tools`. **Recommendation:** `backend/src/abacus_tools/{quality,synthetic,loadtest}` — a second namespaced root, excluded from the runtime wheel, forbidden to `abacus` by import-linter and ruff `TID251`; it may import `abacus` (synthetic seeding and load tests drive the product's public APIs). Alternative: `abacus.tooling.*` inside the product package — simpler single root, but ships test-data generators in the production image and needs the same forbidden contract anyway.
- [x] **Q9 — `ai_gateway` hook protection.** Confirmed 2026-10-05: keep CODEOWNERS-only.
- [x] **Q10 — ADR-024 and ADR-058 frontmatter (blocking `make check-fast`).** Titles contain an unquoted `: `, so the frontmatter is invalid YAML. **Recommendation:** approve a formatting-only edit quoting the two `title:` values (add `docs/adr/ADR-024-need-to-know-metadata-vs-content.md` and `docs/adr/ADR-058-agent-hierarchy.md` to the approval). Loosening the validator would let broken frontmatter through. Approved 2026-10-05 ("lets proceed"); both paths appended to the approval file; titles quoted.
- [x] **Q11 — Local Node toolchain (blocking `make setup` as written).** **Recommendation:** `brew install node@24`, put `/opt/homebrew/opt/node@24/bin` first on `PATH`, then `corepack enable` (installs the `pnpm` shim beside Node 24). Founder's machine change. Approved 2026-10-05: agent ran `brew install node@24` (24.21.0) and `corepack enable`; founder still needs `/opt/homebrew/opt/node@24/bin` first on `PATH` in their shell profile. CODEOWNERS protects `backend/src/ai_gateway/`; the hook does not (pre-existing). **Recommendation:** keep as is (protected-paths.md says "code owners only" during Phase 1); only the path is renamed.

## Handoff
- **Current state:** Steps 0–15 done on `task-001-scaffolding`; `make setup` and `make check-fast` exit 0 with Node 24 + pnpm 12.9.1; every gate proven to fail on a violation.
- **Exact next step:** A **separate session** (amber rule) writes the AC-20 tests listed under *Tests to write* — `backend/tests/unit/quality/test_banned_patterns.py` and `test_validate_docs.py` — without editing `abacus_tools/quality/`. Then run the reviewer agents, push the branch, open the PR for founder review (it changes the hook and CODEOWNERS).
- **Uncommitted or partial work:** none (approval file is git-ignored by design).
- **Known failing checks:** none in stage 1. `make check` (stage 2) is TASK-002's.
- **Open issues:** founder's shell `PATH` still resolves `node` to 20.16 until updated; hook loading in a repo-root session to be confirmed now that the crash is fixed; branch protection deferred; bot GitHub account deferred; TASK-002 file not yet created (must add a hook self-test).
