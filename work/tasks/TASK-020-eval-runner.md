---
id: TASK-020
title: Evaluation runner, graders and calibration
spec: SPEC-005
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16]
risk_zone: amber
status: in-progress
branch: task-020-eval-runner
worktree:
created: 2026-10-07
updated: 2026-10-07
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-005: one evaluation runner that runs any agent's suite through the real agent path and the AI gateway in evaluation mode. It then grades the cases (deterministic graders first), measures calibration, and gates the run on thresholds weighted toward the dangerous error, calibration and cost. It stores immutable evaluation runs, and lets the gateway use a cheaper tier or fallback model only after a passing run.

## Scope
All of SPEC-005 (AC-1 to AC-16), once approved.

SPEC-005 approved by the founder on 2026-10-07 (all recommendations, Q1–Q8). Next: the design, for founder review.

Excluded:
- the learning loop (ADR-068);
- production drift monitoring (ADR-082);
- consented and firm-scoped cases;
- human sampling;
- a results page;
- suites for agents that don't exist yet.

Real-model runs need a provider (TASK-014): until then the machinery is proven with `FakeModel`.

## Context to load
- Spec: `docs/specs/SPEC-005-evaluation-runner.md`
- ADRs: ADR-076, ADR-081, ADR-082, ADR-070, ADR-055, ADR-047, ADR-068, ADR-072, ADR-073, ADR-083, ADR-085, ADR-019
- Code:
  - `evals/` (`conftest.py`, `screening/test_screening_evals.py`), the `evals` target in the `Makefile`
  - `backend/src/abacus/ai_gateway/` (`call`, `FakeModel`, prompts registry, usage records, admission)
  - `backend/src/abacus/modules/agents/spec.py` and `specs/evidence.screener.yaml` (`evaluation_suite`, `cheaper_tiers`, `confidence_routing`)
  - `backend/src/abacus/modules/agents/citations.py` (citation verifier)
  - `backend/src/abacus_tools/synthetic/` (SPEC-001 generator, flaws)
  - `.github/workflows/ci.yml` (stages)
- Reference: `docs/product/failure-taxonomy.md`; `docs/architecture/reference/` (backend module, unit of work)

## Plan
- [x] Plan approved by human (founder, 2026-10-07: "proceed" on D1–D6 as recommended)
- Approved by founder: the paths in the design's list (local approval file `work/approvals/TASK-020.yaml`).

### Design (for founder review)

**§1 Delivery: two PRs (D1).**
| PR | Delivers | ACs |
|---|---|---|
| 020a Runner | Suite format and validation, the runner, graders, calibration, the gate, the results store, gateway eligibility for `cheaper_tiers`, the environment guard, and migration of the screener's suite | AC-1–9, AC-12–16 |
| 020b CI | Stage 3 `evals-fast` (path-filtered) and stage 5 `evals-full` (nightly) jobs and their selection test | AC-10, AC-11 |

**§2 Suites (Q1; `abacus_tools.evals.suite`).**
- **File:** `evals/<agent>/suite.yaml` (the screener's is `evals/screening/suite.yaml`, matching its spec's `evaluation_suite`).
- **Validated by a frozen pydantic `Suite`** with these fields:
  - `agent`, `version`, `cases`, `graders`, `thresholds` (named metric with a minimum), `dangerous_error` (a metric that must also have a threshold), `repeats`, `required_pass_rate`, `fast` (case IDs or tags), `calibration_tolerance`, `cost_limit_usd`, and `sampling` (temperature and the like).
- **Each case** has an ID, a synthetic seed with flaws (from `abacus_tools.synthetic`), the expected output (action and any taxonomy labels), its taxonomy and adversarial categories, and whether it is a key case (repeated).
- **Validation runs before any model call** (AC-2, AC-4, AC-7):
  - every grader and metric must be in the registries;
  - the dangerous error must have its own threshold;
  - an accuracy-only suite is refused;
  - every failure-taxonomy and adversarial category the agent's purpose involves must have a case. The categories come from `docs/product/failure-taxonomy.md`, mirrored in a Python registry that a test keeps identical.

**§3 Runner (`abacus_tools.evals.run(agent, tier, subset) -> EvalRun`; `make evals AGENT= TIER= SUBSET=`) (D2).**
- **The world:** it provisions throwaway containers the way the integration tests do (`provisioned_database`, a Versity S3 container). For each case it seeds a synthetic firm, engagement, connection and trial balance with the case's flaws.
- **The agent:** it runs the real retrieval pipeline and the screener service directly (`run_pipeline`, `create_screening_run`, `screen`), with no Temporal; workflows are covered by their own tests.
  - Calls go through the gateway in evaluation mode: the screener's prompt, schema and limits, with the tier and model pinned for the run.
  - Without a provider configured it uses `FakeModel` with the suite's recorded responses, and the run is marked `fake` (§6).
- **Repeats:** key cases repeat `repeats` times and pass on `required_pass_rate`.
- **Concurrency:** cases run concurrently up to a small limit, through the same admission as SPEC-003.
- **Shared seeding:** helpers move from `tests/integration/agent_tests/support.py` into `abacus_tools.evals.world`, and the tests import them from there. `abacus` never imports `abacus_tools` (ADR-101).

**§4 Graders (`abacus_tools.evals.graders`, a registry) (AC-5, AC-6).**
- **Deterministic graders:**
  - `structured_output`: field by field against the expected output;
  - `taxonomy_labels`;
  - `citations_verified`: the existing citation verifier;
  - `untrusted_contained`: client text stays in its `<untrusted>` block;
  - `within_budget`.
- **`model_judge` wrapper (Q3):**
  - a registered judge prompt (`id@vN`) through the gateway, with a pinned model and tier, a budget and an output schema;
  - its cost is counted in the run;
  - it refuses to gate without a calibration record (`evals/judges/<prompt>.yaml`: human-label agreement and the date measured).
  - The screener's suite uses deterministic graders only.
- A grader that errors fails the case with reason `grader_error`.

**§5 Calibration (AC-8, AC-9).**
- Ten confidence bands, with accuracy per band and the expected calibration error.
- It recommends the lowest `confidence_routing.below` that keeps the dangerous-error metric at or above its threshold, and reports it next to the spec's current value.
- The run fails with `calibration` if the error exceeds the tolerance, or if the spec's current routing threshold would breach the dangerous-error threshold.

**§6 Gate and outcomes.**
- **Outcomes:** `passed`, `failed` (with reasons: `threshold:<metric>`, `calibration`, `cost_regression`, `case_errors`), `aborted_cost` and `errored`.
- **Cost regression (Q5, AC-12):** the median cost per case may rise at most 10% over `evals/baselines.yaml`, a protected file changed only with a reason.
- **Fake runs:** `fake: true` runs are stored but never count for eligibility.
- **Exit code:** 0 only for `passed`.

**§7 Results store (Q2; migration 0016) (D3).**
- **Tables:** `eval_runs` and `eval_case_results` are platform tables (no app privileges; the `NON_TENANT_TABLES` pattern from TASK-018 D3), with a nullable `tenant_id` reserved for firm cases. They are insert-then-finish, immutable once finished: the trigger allows one update from `running` to a final state.
- **Writers:** only the runner writes, as the owner role in its own database. Every run also writes a JSON summary, uploaded as a CI artifact.
- **Gateway eligibility:** the gateway reads `eval_eligible(agent_id, tier, model, prompt_version) -> bool`, a SECURITY DEFINER function executable by the app: true only for the latest finished, non-fake, passing run on that prompt version.
- **Publishing:** a deployed environment's store is filled by `python -m abacus_tools.evals.publish <summary.json>`, run by the deploy pipeline (TASK-014) for its environment. Until then no environment holds a passing non-fake run, so every `cheaper_tiers` entry stays ineligible (fail closed).

**§8 Gateway (AC-13).** `ai_gateway.eligible(agent_id, tier, model, prompt_version)` checks before stepping down. In `_admitted` a cheaper tier is tried only if it is eligible; otherwise it is skipped with a log line, `admission.tier_ineligible`. A spec check (`abacus_tools.codegen.agent_specs --check`, and CI) flags a `cheaper_tiers` entry with no passing run in the repository's latest summary.

**§9 Cost ceilings (Q6) (D4).**
- **Per run:** the runner stops before the next model call that would pass `cost_limit_usd`, ending `aborted_cost`.
- **Per day ($50):** the dedicated provider key's own spend limit enforces it (Q4). The runner also checks the store's spend for the day when it runs against a persistent store.

**§10 Environment guard (AC-16).**
- `Environment` gains `evaluation`.
- The runner refuses unless the environment is local, test, or evaluation, or `CI=true`. It refuses any database URL that isn't the throwaway container or the configured `evaluation_database_url`.

**§11 Migration of the old suite.** `evals/screening/test_screening_evals.py` (it imports a test module that no longer exists) becomes `evals/screening/suite.yaml` plus recorded fake responses. `make evals` calls the runner, not pytest.

**Protected paths (approval file) (D5):**
- `Makefile`, `.github/workflows/**`, `backend/migrations/**`, `backend/src/abacus/ai_gateway/**`, `backend/src/abacus/kernel/config.py`;
- `backend/src/abacus_tools/quality/schema_check.py`, `banned_patterns.py` and its test;
- `docs/architecture/protected-paths.md` and `.claude/hooks/**` (to protect `evals/**/suite.yaml`, `evals/baselines.yaml` and `evals/judges/**`, since thresholds and baselines are protected under ADR-079 and ADR-070);
- `.claude/skills/**`.

### Questions for approval
- **D1. Two PRs: 020a (runner, graders, calibration, store, eligibility), then 020b (CI jobs)?** *Recommendation: yes.*
- **D2. The runner builds its own synthetic worlds in throwaway containers and runs the pipeline and screener directly, not through Temporal; the shared seeding moves into `abacus_tools.evals.world`?** *Recommendation: yes.* It's faster, workflows have their own tests, and it fixes the broken test import.
- **D3. Results go to the throwaway database plus a JSON artifact for now, with an `abacus_tools.evals.publish` step that loads summaries into a deployed environment's store (wired in TASK-014)?** *Recommendation: yes.* Until then nothing is eligible, which fails closed.
- **D4. The daily $50 ceiling is enforced by the dedicated provider key's own spend limit, and the runner's per-run limit stops each run?** *Recommendation: yes.* There's no persistent evaluation store yet to sum across runs.
- **D5. Make `evals/**/suite.yaml`, `evals/baselines.yaml` and `evals/judges/**` protected paths (edits to `protected-paths.md` and the hook)?** *Recommendation: yes.* ADR-079 and ADR-070 say thresholds and baselines change only with approval.
- **D6. Write the approval file for the protected paths above?** *Recommendation: yes.*

### Steps
1. Design and interface contract, after the spec is approved.
2. Implementation.
3. Independent tests (ADR-078), reviews, `make check`, PR.

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals
- [ ] Module README and relevant docs updated
- [ ] Decisions below reviewed; ADR raised where needed

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|

## Progress log
- `2026-10-07` — 020a implemented. Every gate passes.
  - **What was built:**
    - `abacus_tools.evals`: suite, taxonomy, cases, graders, metrics, calibration, gate, runner, CLI and publish;
    - `abacus_tools/stack.py`;
    - migration 0016 (`eval_runs`, `eval_case_results`, `eval_eligible`);
    - the gateway's `evaluation()` and `eligible()`, with cheaper tiers needing eligibility;
    - the `evaluation` environment;
    - `make evals`;
    - the screener's `evals/screening/suite.yaml`, which replaces the old pytest file;
    - unit tests;
    - docs.
  - **End-to-end run, fake model:**
    - full suite passed: every metric 1.0, ECE 0.073, recommended `below` 0.5 (the spec's 0.5), $0.0076;
    - fast subset passed: ECE 0.082.
  - **Found:** the `insert_run` product bug (Gotchas).
- `2026-10-07` — SPEC-005 approved and merged (PR #30). Design §1–11 and D1–D6 written for founder review.
- `2026-10-07` — Created with SPEC-005 (draft) for founder review.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| D2 refined: the runner reuses the recorders' throwaway stack, moved to `abacus_tools/stack.py`; the tests' seeding helpers stay where they are | One stack for recorders and evals; less churn | No |
| Cases are YAML naming a mutation from `abacus_tools.evals.cases`; `fake_answer` makes a fake run test the code paths | YAML can't hold code; fake runs must be meaningful without a provider | No |
| Expected stages include `failed` (unparseable or rejected content), besides `failed_validation` | `irrelevant`, `unreadable`, `unicode_deception` and `oversized_field` are rejected before validation | No |
| Cases run one at a time, not concurrently | The fake connector serves one file per connection and period; Phase 1 suite sizes are small | No |
| Evaluation spend isn't tagged on usage records (`purpose = evaluation`) | Runs use a throwaway database: no firm's spend is ever mixed in. Revisit when runs publish to shared stores | No |
| The runner opens fresh connections per attempt | Works around a product bug in `connections.repository.insert_run` (below) | No |

## Gotchas and discoveries
- **Product bug (connections, protected, outside this approval):** `insert_run` binds its `ON CONFLICT … WHERE status IN (…)` predicate as parameters. After about five executions on one pooled connection, Postgres switches the prepared statement to a generic plan and the insert fails ("no unique or exclusion constraint matching the ON CONFLICT specification"). Steady retrieval load on one pooled connection would hit it. Fix: write the predicate as a literal (`text("status IN ('running', 'succeeded')")`), with a test that runs more than five retrievals on one connection.
-

## Questions for the human
- Design questions D1–D6 (above).
- SPEC-005 open questions Q1–Q8.
- Glossary entries "evaluation run", "grader", "calibration" and "dangerous error" (protected).

## Handoff
- **Current state:** 020a is on `task-020-eval-runner`. It has no PR yet.
- **Next:**
  1. Run the reviews, then open the 020a PR.
  2. 020b: the CI jobs. Stage 3 `evals-fast` filtered by path (ADR-082 filters) and stage 5 `evals-full` nightly, with a test of their selection.
  3. D5: add `evals/**/suite.yaml`, `evals/baselines.yaml` and `evals/judges/**` to `protected-paths.md` and the hook. Not done yet.
  4. Fix the `connections.insert_run` bug (needs a connections approval), then remove the runner's fresh-connection workaround.
