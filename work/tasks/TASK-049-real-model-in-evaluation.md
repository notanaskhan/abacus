---
id: TASK-049
title: A real model in evaluation, behind a data boundary in code
spec: SPEC-026
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: red
status: planned
branch: task-049-real-model-eval
worktree:
created: 2026-10-10
updated: 2026-10-10
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
All of SPEC-026:
- the three-layer data boundary;
- pinned real models on the direct route;
- real-mode evaluation runs;
- the milestone report.

The code ships without credentials. The milestone run happens once you've provided the key and confirmed the model IDs (D1, D2).

## Scope
SPEC-026 AC-1 to AC-8.

## Context to load
- Spec: `docs/specs/SPEC-026-real-model-in-evaluation.md`; ADR-019, ADR-031, ADR-074; SPEC-010 (routes, parity)
- Code:
  - `kernel/config.py` (`Settings`, `SYNTHETIC_ENVIRONMENTS`, `CatalogModel`, `model_routes`, `model_catalog`, `anthropic_api_key`);
  - `ai_gateway/__init__.py` (`_call`, the route-provider call at :644; `embed`, :348);
  - `ai_gateway/routes/` (`direct.py` exists);
  - `abacus_tools/evals/runner.py` (`_attempt` installs `FakeModel`; the run pins `route="fake"`), `summary.py`, `metrics.py`;
  - `abacus_tools/stack.py` and `local/seed_dev.py` (where firms are inserted).

## Plan
- [ ] Plan approved by human

### What the code shows
- **The direct route already works** (`AnthropicDirect`, behind admission and parity). The catalog is fake by default; the runner installs the fake model and records `route="fake"`.
- **The only places a model is called** are `ai_gateway._call` (`route_provider(route).complete`) and `embed` (`embedder().embed`). A boundary check before those two calls covers every path.
- **The gateway doesn't import modules.** It can't read `firms` itself, because identity owns that table.
- **Firms in synthetic environments are inserted in two places:** the evaluation stack (`stack.py`) and the local seed.

### Design (for founder review)
1. **Settings (AC-1, AC-4, AC-8),** in `kernel/config.py`:
   - `model_data_boundary: Literal["synthetic_only"] = "synthetic_only"`. Any other value fails validation, with a message naming the later spec it needs.
   - `allow_real_model_locally: bool = False`.
   - **A validator refuses a real route** (`direct` or `bedrock`) in `model_routes`, or as the embedding provider:
     - in `staging`, `production` and `test`;
     - in `local` unless `allow_real_model_locally`;
     - it's allowed in `evaluation`.
   - **A validator refuses unpinned IDs:** every real-route ID in `model_catalog` must match `^claude-[a-z]+-\d+-\d+(-\d{8})?$` (no `latest`, no bare family). The exact IDs come from D1.
   - **Real catalog defaults:** `_anthropic_catalog()` with D1's pinned IDs and prices for `direct`, used when `model_routes` includes `direct` and no catalog is given. The fake catalog stays the default.
   - The key stays `SecretStr`, and errors hide inputs (already).
2. **Per-call boundary (AC-2),** in the gateway:
   - a registration slot `register_synthetic_tenants(check: Callable[[TenantContext], Awaitable[bool]])`;
   - identity registers it from `identity/api.py`; unregistered means refused;
   - before the provider call in `_call` and `embed`, for any route other than `fake`: if the check says no, raise `DataBoundaryRefused` (never retried, never routed elsewhere), audit `ai.boundary_refused` (tenant, prompt, route, never content) and count `abacus.ai.boundary_refused`;
   - the answer is cached per process for 60 seconds.
3. **`firms.synthetic` (AC-3),** identity migration 0038:
   - a boolean, default false;
   - not in the app role's insert or update grants;
   - the evaluation stack and the local seed set it `true`, through the owner role;
   - identity's check reads it under the call's tenant session (the app may read `firms`).
4. **Real-mode runs (AC-5, AC-7):**
   - `python -m abacus_tools.evals --route direct` (`make evals EVAL_ARGS="--route direct"`);
   - in real mode, `_attempt` doesn't install the fake model, `fake_answer` is ignored, and the run is pinned with `evaluation(tier, route="direct")`;
   - the summary records `fake=False`, the route, and the exact model ID from the catalog;
   - `cost_limit_usd` is enforced before each case (exists);
   - with real mode outside `ABACUS_ENVIRONMENT=evaluation`, or with no key, the runner stops before starting containers.
5. **The milestone report (AC-6):** the summary gains:
   - needs-revision recall with its misses (case and category);
   - recall per taxonomy category and containment per adversarial category;
   - ready precision;
   - cost per screening (mean, p95, maximum, and the count over the spec's `max_cost_usd`), and the total against `cost_limit_usd`;
   - escalations to `medium`, ECE, and latency p50/p95.

   A plain table prints at the end. Fake runs fill the same fields, which is how the tests cover them.
6. **Parity:**
   - with the key, `make route-parity ROUTE=direct` writes `docs/operations/route-parity/direct-<date>.json` (identifiers and results only), committed with the milestone;
   - then `model_routes` for evaluation is `[direct]`, set by environment variable, not committed.
7. **Baselines:** after the first passing real run, `evals/baselines.yaml` is proposed for your approval (SPEC-026 Q5). It's a protected path, approved separately when the file exists.
8. **Tests:**
   - settings validation across environments and IDs;
   - the gateway refusing with a provider stub that fails if called, plus cache and audit;
   - grants on `firms.synthetic` (integration);
   - the runner's real-mode guards;
   - summary fields from a fake run.

   The milestone itself is one real run, with its report attached to the progress log.

**Protected paths (approval file), each named:**
- `backend/src/abacus/ai_gateway/**`: the boundary check, the slot, `DataBoundaryRefused`, `embed`;
- `backend/src/abacus/modules/identity/*` (top-level): registering the check;
- `backend/src/abacus_tools/quality/schema_check.py`: `firms.synthetic` kept out of the app's grants;
- `docs/operations/route-parity/**`: the parity report from the milestone;
- `backend/tests/unit/**` and `backend/tests/integration/**`: the grant test.

Not protected but changed:
- `kernel/config.py` (only `kernel.db`, `.uow`, `.crypto` and `.storage` are protected);
- `abacus_tools/evals/**`, `abacus_tools/stack.py`, `abacus_tools/local/seed_dev.py`;
- the new migration file.

Not touched: `evals/screening/suite.yaml` (thresholds unchanged), the agents module, `api/app.py`, the worker.

### Questions for approval
- **D1. The pinned model IDs and prices per tier.** SPEC-026 Q1 is approved as "you confirm from the provider console". Please send:
  - `small`: `claude-haiku-4-5-20251001`? Its input and output price per million tokens?
  - `medium` (Claude Sonnet 5.5) and `large` (Claude Opus 5.5): their exact IDs as your console shows them, and prices.

  Until then the code ships with the fake catalog default, and the real catalog fails validation if any ID is missing.
- **D2. The evaluation key.** When it's ready, put it in your shell (`export ABACUS_ANTHROPIC_API_KEY=…`, never committed): a separate workspace, the $50/day cap and zero retention if offered. I'll then run parity and the milestone.
- **D3. Write the approval file for the paths above?** *Recommendation: yes.*

## Definition of done
- [ ] All listed ACs have passing tests that reference them (independent tests deferred by the founder)
- [ ] Type check, lint, format, architecture and dependency rules pass
- [ ] Every query is tenant-scoped; every endpoint checks authorisation
- [ ] Module READMEs and the relevant docs are updated
- [ ] The milestone real run's report is in the progress log (after D1 and D2)

## Progress log
- `2026-10-10` — Design written for founder review after SPEC-026 merged (#86).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|

## Handoff
