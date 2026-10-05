---
id: TASK-002
title: Complete stage 1, make check pass, and run both stages in CI
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-progress
branch: task-002-stage-gates
worktree:
created: 2026-10-05
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
Finish the stage 1 gates ADR-083 lists but `make check-fast` does not yet run (secrets and real-identifier scan, dependency allowlist), make `make check` (stages 1 + 2) pass honestly on the pre-SPEC-000 codebase, and run both stages in GitHub Actions (build plan §5.1 step 3, second half). Runs before any SPEC-000 work (TASK-001 Q1).

## Scope
**In**
- `abacus_tools.quality.secrets_scan` — secrets and real-identifier scan of git-tracked files (ADR-083, ADR-085)
- `abacus_tools.quality.check_dependencies` — every direct dependency in `backend/pyproject.toml` and every `package.json` is `approved` in the allowlist, in the right section (runtime vs dev) (AGENTS.md rule 12)
- Banned pattern `SKIP-001`: `pytest.mark.skip` / `skipif` / `xfail` / `pytest.skip()` without an issue reference (ADR-079)
- pytest configuration (`--import-mode=importlib`, strict markers, `asyncio_mode`), and "no tests collected" handled honestly for still-empty suites
- Stage 2 targets that need code SPEC-000 hasn't written yet: `schema_check`, API-client drift, vitest — each runs and passes on the current tree without faking a result (Q3)
- Coverage floors in a protected thresholds file (ADR-079) — **if Q2 approves `pytest-cov`**
- `Makefile`: wire the new stage 1 checks into `check-fast`; stage 2 adjustments from Q3
- `.github/workflows/ci.yml`: stage 1 on every push, stages 1 + 2 on every PR (Q4)
- Docs: AGENTS.md command list unchanged; `protected-paths.md` gains the thresholds file and workflow

**Out**
- Classification-tag check (ADR-031): no models exist and the tag mechanism is a kernel design in SPEC-000 — Q1
- Real schema / RLS checks, permission-matrix tests, route introspection, tenant isolation suite (ADR-080) — they need tables, routes and the matrix wiring from SPEC-000
- Stages 3–5 (build plan step 7)
- Turning on branch protection (founder's GitHub setting; recommended right after this task so the new CI jobs become required checks)

## Context to load
- ADRs: ADR-083 (stages), ADR-079 (coverage, skip rule), ADR-085 (identifier scan), ADR-077 (test layers), ADR-080 (security suite), ADR-031 (classification), ADR-101 (layout)
- Spec: `docs/specs/SPEC-000-walking-skeleton.md` §5 AC-20, §18
- Code: `Makefile`, `backend/pyproject.toml`, `backend/src/abacus_tools/quality/`, `backend/tests/unit/quality/`, `docs/architecture/dependency-allowlist.yaml`
- Reference pattern: `banned_patterns.py` / `validate_docs.py` (CLI shape, output format, exit codes, tests)

## Plan
- [x] Plan approved by human (founder, 2026-10-05: "approved, write the approval file and proceed")
- [x] Approval file `work/approvals/TASK-002.yaml` written **by the agent at the founder's explicit instruction** (2026-10-05)
- Approved by founder: paths listed under *Approval file text*, expires 2026-10-19
- [x] Questions Q1–Q4 answered: all recommendations approved (2026-10-05)

Steps:

1. [ ] **`secrets_scan.py`** — `python -m abacus_tools.quality.secrets_scan`; scans `git ls-files` output (tracked + staged), skips binaries and lockfiles' integrity hashes. Rules (frozen dataclasses, same shape as `banned_patterns`):
   | Rule | Detects |
   |---|---|
   | `SECRET-001` | Private key blocks (`-----BEGIN … PRIVATE KEY-----`) |
   | `SECRET-002` | Provider tokens with fixed prefixes: AWS access key ids (`AKIA…`/`ASIA…`), GitHub (`ghp_`, `github_pat_`, `gho_`…), Anthropic (`sk-ant-`), OpenAI (`sk-proj-`, `sk-`+48), Slack (`xox?-`), Stripe (`sk_live_`), Google API keys (`AIza…`) |
   | `SECRET-003` | Assignment of a non-placeholder literal to a name matching `*_KEY`, `*SECRET*`, `*TOKEN*`, `*PASSWORD*` in `.py`, `.ts`, `.yaml`, `.toml`, `.env*`, `.json` (placeholders like `changeme`, `<…>`, `${…}`, `""` allowed) |
   | `PII-001` | US SSN shape `NNN-NN-NNNN` outside the invalid ranges (000, 666, 9xx, 00, 0000) (ADR-085) |
   | `PII-002` | EIN shape `NN-NNNNNNN` with a valid IRS prefix, in data-like files (`.csv`, `.json`, `.yaml`, `.xlsx` text, fixtures) |
   | `PII-003` | Card numbers 13–19 digits passing Luhn; ABA routing numbers passing the ABA checksum when labelled (`routing`, `aba`) |
   Exceptions only via exclude globs in the file (protected). Synthetic data must use reserved ranges (SSN `9xx`, test card numbers) — the generator (build plan step 4) follows this. Output and exit codes as `banned_patterns`.

2. [ ] **`check_dependencies.py`** — `python -m abacus_tools.quality.check_dependencies`. Reads `[project].dependencies` (→ `python.runtime`) and `[dependency-groups]` (→ `python.dev`) from `backend/pyproject.toml`, and `dependencies` / `devDependencies` / `peerDependencies` / `optionalDependencies` from every tracked `package.json` (→ `typescript.runtime` / `.dev`). Names normalised (PEP 503 for Python; scoped names and `@scope/*` globs for npm). Fails on: not listed, listed as `pending`, runtime dependency listed only under `dev`. Direct dependencies only — transitive ones are fixed by the lockfiles and audited in stage 3 (`pip-audit`, already approved). Also fails if `uv.lock` is out of date (`uv lock --check`).

3. [ ] **`SKIP-001`** in `banned_patterns.py`: `@pytest.mark.skip`, `skipif`, `xfail`, `pytest.skip(...)`, `pytest.xfail(...)` need a `reason=` containing an issue reference (`#123` or a GitHub issue URL) (ADR-079).

4. [ ] **pytest configuration** in `backend/pyproject.toml`: `addopts = "--import-mode=importlib --strict-markers --strict-config"`, `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `xfail_strict = true`. In `tests/conftest.py`: a session-finish hook that turns pytest's exit 5 ("no tests collected") into 0 **only** when none of the selected directories contains a `test_*.py` file — an empty suite passes, a mis-filtered run still fails. Removed once every suite has tests.

5. [ ] **Stage 2 targets before SPEC-000** (Q3 decides the shape; recommendation):
   - `abacus_tools.quality.schema_check`: real entry point; with no migrations in `backend/migrations/versions/` it prints "no migrations yet" and exits 0; with any migration it exits 1 "schema_check not implemented" — so SPEC-000's first migration is forced to bring the real check
   - API-client drift: `Makefile` `check` runs it only when `backend/src/abacus/api/main.py` exists; otherwise prints the skip. Same forcing function: SPEC-000's entry point turns it on
   - vitest: one real smoke test `apps/web/src/App.test.tsx` rendering `<App />` with `@testing-library/react` (approved) — needs a DOM environment, `jsdom` or `happy-dom`, **not approved** (Q2)

6. [ ] **Coverage floors** (if Q2 approves `pytest-cov`): `docs/architecture/test-thresholds.yaml` (protected) holding the floor per area (global, red-zone modules) per ADR-079; `make check` reads it. Initial floor: 90 % for `abacus_tools.quality` (currently tested), others start at 0 % and are raised by the tasks that add code — the file is protected, so every change gets founder review.

7. [ ] **Makefile** — `check-fast` gains `secrets_scan` and `check_dependencies`; `check` gains the step 5 guards and coverage. Nothing removed.

8. [ ] **CI** `.github/workflows/ci.yml` (Q4): `stage-1` job on every push (`make setup && make check-fast`), `stage-2` job on pull requests (`make check`); Node 24, Python via `uv`, pnpm via corepack; actions pinned to full commit SHAs; `permissions: contents: read`; no secrets used. Concurrency cancels superseded runs.

9. [ ] **Verify:** `make check-fast` and `make check` exit 0 locally and in CI on the PR. Gate-break each new check (one planted secret per `SECRET-*`, one identifier per `PII-*`, an unlisted and a `pending` dependency, a dev-only runtime dep, a reasonless skip, a coverage drop, a stale `uv.lock`), confirm failure, revert.

Files to create or change:
- `backend/src/abacus_tools/quality/{secrets_scan,check_dependencies,schema_check}.py`, `banned_patterns.py` *(protected)*
- `backend/tests/unit/quality/test_secrets_scan.py`, `test_check_dependencies.py`, `test_schema_check.py`, `test_banned_patterns.py` (SKIP-001 cases) *(protected)*
- `backend/pyproject.toml`, `backend/uv.lock` *(protected)*; `backend/tests/conftest.py`
- `Makefile` *(protected)*
- `.github/workflows/ci.yml` *(protected)*
- `docs/architecture/test-thresholds.yaml` *(new; added to the protected list)*, `docs/architecture/protected-paths.md`, `.claude/hooks/_protected.py`, `.github/CODEOWNERS` *(protected)*
- `docs/architecture/dependency-allowlist.yaml` *(protected; only for Q2-approved packages)*
- `apps/web/package.json`, `pnpm-lock.yaml` *(protected)*, `apps/web/src/App.test.tsx`, `apps/web/vite.config.ts` (vitest environment)

Tests to write (mapped to ACs) — amber: separate session unless the founder waives it again:
- AC-20 → `test_secrets_scan.py`: `test_ac20_<rule>_flags_violation` / `_allows_clean` per rule; placeholder values allowed; synthetic reserved ranges allowed; untracked files ignored
- AC-20 → `test_check_dependencies.py`: unlisted, pending, wrong section, scoped glob match, PEP 503 normalisation, clean manifests pass, real repo passes
- AC-20 → `test_banned_patterns.py`: SKIP-001 cases
- AC-20 → `test_schema_check.py`: no migrations → 0; a migration present → 1
- AC-20 → `make check` exits 0 locally and in CI (step 9)

### Interface contract (tests are written against this, independently of the code — ADR-078)

All three checkers live in `abacus_tools.quality`, follow `banned_patterns`' shape, and have `main() -> int` (0 clean, 1 violations; one line per violation on stdout).

**`secrets_scan`**
- `scan(repo: Path, files: Iterable[str] | None = None) -> list[Violation]` — `files` are repo-relative POSIX paths; `None` means `git ls-files` in `repo`. Returns violations sorted by (path, line, rule_id). `Violation` is `banned_patterns.Violation` (same `str()` format: `path:line: RULE-ID message (ADR-…)`).
- **Messages never contain the matched value** (they reach CI logs).
- Skipped: files listed in `EXCLUDE` globs (fnmatch, repo-relative), `uv.lock`, `pnpm-lock.yaml`, files containing a NUL byte, files over 1 MB, missing files.
- `SECRET-001` (ADR-083): a line containing `-----BEGIN` … `PRIVATE KEY-----`.
- `SECRET-002` (ADR-083): tokens `AKIA`/`ASIA` + 16 `[A-Z0-9]`; `ghp_|gho_|ghu_|ghs_|ghr_` + 36 alnum; `github_pat_` + 22+ `[A-Za-z0-9_]`; `sk-ant-` + 20+ `[A-Za-z0-9_-]`; `sk-proj-` + 20+; `sk-` + 48 alnum; `xox[abprs]-` + 10+ `[A-Za-z0-9-]`; `sk_live_` + 16+ alnum; `AIza` + 35 `[A-Za-z0-9_-]`.
- `SECRET-003` (ADR-083): `NAME = "value"` / `NAME: "value"` / `NAME="value"` (quotes optional for `.env*` and YAML) where NAME contains `KEY`, `SECRET`, `TOKEN`, `PASSWORD` or `PASSWD` (case-insensitive) and value is ≥ 8 chars with no whitespace and is not a placeholder. Placeholders: empty; starts with `<`, `${`, `{{`, `$`; contains (case-insensitive) `changeme`, `example`, `placeholder`, `dummy`, `fake`, `test`, `xxx`, `redacted`; a single repeated character.
- `PII-001` (ADR-085): SSN `\b\d{3}-\d{2}-\d{4}\b` unless area is `000`, `666` or `9xx`, group `00`, or serial `0000`. All scanned files.
- `PII-002` (ADR-085): EIN `\b\d{2}-\d{7}\b` with an IRS-assigned prefix (01–06, 10–16, 20–27, 30–48, 50–68, 71–77, 80–88, 90–95, 98, 99), only in data-like files: `.csv`, `.json`, `.yaml`, `.yml`, `.txt`, `.tsv`.
- `PII-003` (ADR-085): 13–19 consecutive digits (spaces/hyphens between groups allowed) passing Luhn, unless a published test card (`4111111111111111`, `4242424242424242`, `5555555555554444`, `5105105105105100`, `378282246310005`, `371449635398431`, `6011111111111117`, `3530111333300000`); or 9 digits passing the ABA checksum on a line that also contains `routing` or `aba` (case-insensitive).

**`check_dependencies`**
- `check(repo: Path) -> list[str]` — sorted messages; empty when clean. Reads `docs/architecture/dependency-allowlist.yaml`, `backend/pyproject.toml`, and every `package.json` under `repo` except inside `node_modules`, `dist` or dot-directories.
- Python names: PEP 503-normalised (`lower`, runs of `-_.` → `-`), version/extras/markers stripped. `[project].dependencies` must be approved in `python.runtime`; `[dependency-groups].*` approved in `python.dev` or `python.runtime`.
- npm: `dependencies`, `peerDependencies`, `optionalDependencies` → `typescript.runtime`; `devDependencies` → `typescript.dev` or `typescript.runtime`. Allowlist keys may be globs (`@radix-ui/*`). Entries whose version starts with `workspace:` are skipped.
- Messages (`<rel>` = repo-relative manifest path):
  - `<rel>: <name> is not in the dependency allowlist`
  - `<rel>: <name> is pending in the dependency allowlist, not approved`
  - `<rel>: <name> is approved only as a dev dependency`

**`schema_check`**
- `check(migrations: Path) -> list[str]` — `[]` if the directory is missing or holds no `*.py` other than `__init__.py`; otherwise exactly one message: `schema_check is not implemented: SPEC-000 must add the tenant and row-level security schema check with its first migration`. `main()` uses `backend/migrations/versions`.

**`banned_patterns` `SKIP-001`** (ADR-079): `pytest.mark.skip`, `pytest.mark.skipif`, `pytest.mark.xfail` (as decorator, called or bare) and calls `pytest.skip(...)`, `pytest.xfail(...)`, `pytest.importorskip(...)` are violations unless a `reason` (keyword, or first positional string for `skip`/`xfail`) contains `#<digits>` or `github.com/<owner>/<repo>/issues/<digits>`. One finding per offending node.

### Approval file text
`work/approvals/TASK-002.yaml` (exact paths; extended only for Q2 packages):
```yaml
task: TASK-002
approved_by: founder
expires: 2026-10-19
paths:
  - Makefile
  - .github/workflows/ci.yml
  - .github/CODEOWNERS
  - .claude/hooks/_protected.py
  - docs/architecture/protected-paths.md
  - docs/architecture/test-thresholds.yaml
  - docs/architecture/dependency-allowlist.yaml
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/src/abacus_tools/quality/secrets_scan.py
  - backend/src/abacus_tools/quality/check_dependencies.py
  - backend/src/abacus_tools/quality/schema_check.py
  - backend/src/abacus_tools/quality/banned_patterns.py
  - backend/tests/unit/quality/test_secrets_scan.py
  - backend/tests/unit/quality/test_check_dependencies.py
  - backend/tests/unit/quality/test_schema_check.py
  - backend/tests/unit/quality/test_banned_patterns.py
  - apps/web/package.json
  - pnpm-lock.yaml
reason: TASK-002 — stage 1 completion, make check, CI
```

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass — now including `check_dependencies`
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed — now including `secrets_scan`
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation — n/a, no queries or endpoints
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals — n/a
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed
- [ ] `make check` exits 0 locally and both CI jobs pass on the PR

Commands:
```
make setup
make check-fast
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| pytest-cov (py dev) | pinned in `uv.lock` | Coverage floors (ADR-079) | Founder, 2026-10-05 (Q2) |
| jsdom (ts dev) | pinned in `pnpm-lock.yaml` | DOM for the vitest smoke test | Founder, 2026-10-05 (Q2) |
| GitHub Actions: `actions/checkout`, `actions/setup-node`, `astral-sh/setup-uv` | pinned SHAs | CI | Founder, 2026-10-05 (Q4) |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-05` — Task created with plan after TASK-001 merged (PR #1). Awaiting founder approval. No code written.
- `2026-10-05` — Founder approved plan and Q1–Q4; agent wrote the approval file at founder's instruction. Implementation started.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Secrets and identifier scan written in-house, not gitleaks/detect-secrets | No new binary or package; same rule/exclude/test pattern as `banned_patterns`; covers ADR-085 identifiers that generic scanners don't | no |
| Allowlist checks direct dependencies only | Transitive deps are pinned by lockfiles and audited in stage 3 | no |
| Empty-suite handling in conftest, not a plugin | No new dependency; refuses to hide a mis-filtered run | no |
| Stage 2 checks for code that doesn't exist yet fail once that code appears | Forces SPEC-000 to deliver the real check instead of leaving a stub | no |

## Gotchas and discoveries
- `make check` today fails on `pytest tests/unit tests/property` (exit 5: nothing collected in `property`), then on missing `schema_check`, `export_openapi`, `packages/api-client` and vitest.
- Hook self-test, planned here in TASK-001, already landed as `backend/tests/unit/quality/test_hooks.py`.
- Founder's shell `PATH` still resolves `node` to 20.16 — `make` needs `/opt/homebrew/opt/node@24/bin` first.
- Branch protection is off: CI jobs from this task only gate merges once they are required checks.

## Questions for the human
- [x] **Q1 — Classification-tag check.** Approved as recommended 2026-10-05. ADR-083 puts it in stage 1, but there are no models and the tag mechanism (`Annotated[..., Restricted]` vs `Field(json_schema_extra=…)`) is a kernel decision. **Recommendation:** build it in SPEC-000 with the first model and the kernel's classification type; not in this task.
- [x] **Q2 — New dependencies.** Approved as recommended 2026-10-05. `pytest-cov` (coverage floors, ADR-079) and `jsdom` (DOM for vitest). **Recommendation:** approve both; alternatives are hand-rolled coverage (no) and `happy-dom` (faster, less complete — fine too if you prefer).
- [x] **Q3 — Stage 2 before SPEC-000.** Approved as recommended 2026-10-05. Recommendation as in step 5: `schema_check` passes only while there are no migrations, API-client drift runs only once `abacus/api/main.py` exists, vitest gets one real smoke test. Each turns itself on (or fails) when SPEC-000 adds the code. Alternative: keep `make check` red until SPEC-000.
- [x] **Q4 — CI.** Approved as recommended 2026-10-05. GitHub Actions with three third-party actions pinned by SHA, no secrets, read-only token. **Recommendation:** approve, then turn on branch protection with both jobs as required checks.

## Handoff
- **Current state:** Plan written; not approved. No code. Branch `task-002-stage-gates` created; TASK-001 marked done.
- **Exact next step:** Founder answers Q1–Q4, approves the plan, creates `work/approvals/TASK-002.yaml` by hand from *Approval file text*. Then step 1.
- **Uncommitted or partial work:** this file and the TASK-001 status change.
- **Known failing checks:** `make check` (see Gotchas).
- **Open issues:** branch protection off; founder `PATH`; bot GitHub account deferred.
