---
id: SPEC-026
title: "A real model in evaluation: the screener's first measured run"
status: draft
owner: founder
risk_zone: red
related_adrs: [ADR-005, ADR-019, ADR-031, ADR-050, ADR-052, ADR-055, ADR-070, ADR-073, ADR-074, ADR-079]
related_specs: [SPEC-000, SPEC-003, SPEC-005, SPEC-010]
created: 2026-10-10
updated: 2026-10-10
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
For the first time, a real model answers through the AI gateway, for **development and evaluation only, on synthetic data only**. The milestone: the `evidence.screener` evaluation suite runs against a pinned real model, on synthetic-generator documents covering every failure-taxonomy category. It reports:
- recall on "needs revision" (the dangerous error: a bad document proposed as ready);
- cost per screening against the screener spec's budget.

No client data can reach a model. That's enforced in code, in three layers, until zero-retention and no-training terms are in place and staging exists (ADR-031). Lifting the boundary is a later spec.

Wording used from here on: **the platform retrieves and suggests by rule; agents screen and propose.**

## 2. Problem and context
- Every evaluation run so far is fake. Each case's scripted `fake_answer` proves the code handles answers correctly (routing, citations, containment, calibration, the gate), not that any model gets the cases right.
- The provider code already exists (SPEC-010): `ai_gateway/routes/direct.py` (Anthropic's API) and `routes/bedrock.py`, behind route admission and parity checks. The model catalog is fake (`fake-small`, …), and the runner pins `route="fake"`.
- **ADR-031 is policy only today:** "model provider terms must include zero retention and no training before client data is sent". Nothing in code would stop a real route, once configured in staging or production, from receiving client evidence.
- ADR-074 requires exact model versions. Nothing yet rejects an alias such as `-latest`.

## 3. Actors
| Actor | Role here |
|---|---|
| Founder | Creates the evaluation-only provider key (with a spend cap); approves model choices, the baselines file and any prompt change |
| Developer (agent or person) | Runs `make evals` in real mode locally, in the `evaluation` environment |
| AI gateway (code) | The only path to the model; enforces the data boundary on every call |
| Evaluation runner (code) | Seeds synthetic firms and documents, runs the real screener, grades, reports |

## 4. Goals and non-goals
**Goals**
1. **A data boundary in code, in three layers:**
   - **Settings:**
     - `model_data_boundary` is `synthetic_only`, the only value this spec allows; any other value fails settings validation, naming the later spec it needs;
     - real routes (`direct`, `bedrock`) are refused in `staging` and `production`, and in `test` (tests never spend);
     - they're allowed in `evaluation`, and in `local` only with an explicit `allow_real_model_locally` (Q3);
     - so the API and worker refuse to boot anywhere a real route could meet client data.
   - **Per call:** before any network call, the gateway refuses a real-route call unless the call's tenant is marked synthetic (`firms.synthetic`, Q2):
     - the refusal is a non-retryable `DataBoundaryRefused`, audited `ai.boundary_refused`, and counted;
     - no bytes leave.
   - **Who marks a firm synthetic:** only the evaluation runner's seeding and the local seed, through the owner role. The app role can't insert or change the column, and no API sets it.
2. **Pinned models (ADR-074):**
   - catalog entries for the `direct` route with exact, dated model IDs, and their prices per million tokens (Q1);
   - settings validation rejects any ID without a snapshot version or containing `latest`;
   - usage records and spans carry the exact ID, as they do today.
3. **The direct route only:**
   - Bedrock waits for AWS (TASK-014);
   - the screener's spec allows `[bedrock, direct]`, and with Bedrock not enabled, admission uses `direct`;
   - `make route-parity ROUTE=direct` must pass first (SPEC-010 AC-5), and its report is committed.
4. **Real-mode evaluation runs:**
   - `make evals EVAL_ARGS="--route direct"` runs the full suite through the real screener: `fake_answer` is ignored, and the exact model and route are recorded;
   - repeats, `temperature: 0.0`, the suite's `cost_limit_usd` ($5, abort before exceeding) and the key's own $50/day cap (TASK-020 D4) all apply unchanged.
5. **The milestone report** (JSON, plus a short table printed at the end):
   - **needs-revision recall** overall (the dangerous error), with every miss listed by case and category;
   - recall per failure-taxonomy category (all 11) and containment for each adversarial category (all 6);
   - **ready precision** (clean documents wrongly sent back);
   - **cost per screening:** mean, p95 and maximum, against the spec's `limits.max_cost_usd` ($0.03), with the number of screenings over it; total run cost against `cost_limit_usd`;
   - escalations to the `medium` tier, calibration (ECE), and latency p50/p95;
   - pass or fail against the suite's existing thresholds (needs-revision recall ≥ 0.97, ready precision ≥ 0.85, adversarial containment 1.0, citation verification 1.0), which this spec doesn't change.
6. **Baselines:** the first passing real run proposes `evals/baselines.yaml` (cost per case), which the founder approves (Q5). Later runs compare against it, allowing at most 10% over.

**Non-goals**
- Any client data, anywhere. Staging and production stay on the fake model.
- Bedrock, shadow mode and staged rollout (the rest of ADR-074).
- Tier step-down eligibility: that needs a signed, CI-run evaluation (SPEC-005), which comes with staging.
- Changing the screener's prompt or the suite's thresholds. If the real model misses a threshold, prompt work is a follow-up task, and thresholds are never lowered (Q6).
- New agents. The engagement agent is SPEC-027, which needs no model.

## 5. User stories and acceptance criteria
- **AC-1** Given `environment` is `staging`, `production` or `test`, when settings enable a real route, then settings validation fails and the process doesn't start. Given `local` without `allow_real_model_locally`, the same. Given `model_data_boundary` other than `synthetic_only`, the same, in every environment.
- **AC-2** Given a real-route call whose tenant isn't marked synthetic, then the gateway refuses it before any network call (a stub provider proves it was never called), records `ai.boundary_refused`, and raises `DataBoundaryRefused`, which isn't retried.
- **AC-3** Given the application role, then it can't insert or update `firms.synthetic`. Only the local seed and the evaluation runner's seeding set it, through the owner role.
- **AC-4** Given a catalog entry for a real route whose model ID has no snapshot version or contains `latest`, then settings validation fails.
- **AC-5** Given `--route direct`, then the runner runs every case of `evals/screening` through the real screener on the direct route. It ignores `fake_answer`, records the exact model ID and route on the run, and covers every taxonomy and adversarial code the suite declares.
- **AC-6** Given a completed real run, then its summary holds:
  - needs-revision recall with its misses;
  - per-category recall and containment;
  - ready precision;
  - cost per screening (mean, p95, maximum, count over `max_cost_usd`) and the total against `cost_limit_usd`;
  - escalations, ECE and latency;
  - the gate's verdict.
- **AC-7** Given the next case would pass `cost_limit_usd`, then the run stops as `aborted_cost` before making it.
- **AC-8** Given the provider key, then it never appears in logs, errors, summaries or validation messages (`SecretStr`, `hide_input_in_errors`).

## 6. Behaviour and flows
1. The founder creates an evaluation-only key with a daily spend cap and puts it in the local environment (`ABACUS_ANTHROPIC_API_KEY`). It isn't committed.
2. The developer runs `make route-parity ROUTE=direct`, which writes and commits the parity report.
3. The developer runs `make evals EVAL_ARGS="--route direct"` with `ABACUS_ENVIRONMENT=evaluation`:
   - throwaway containers start, and synthetic firms are seeded with `synthetic = true`;
   - each case seeds a synthetic trial balance carrying its mutation (`abacus_tools.evals.cases`), runs the real retrieval pipeline, then the screener through the gateway;
   - the gateway checks the boundary, then calls the pinned model.
4. The report prints, and the JSON summary is written.
5. If the run passes, the founder approves `evals/baselines.yaml` from it.

## 7. Domain and data changes
- **`firms.synthetic`** (boolean, default false): owner-set only; no app grant.
- **Settings:** `model_data_boundary` (`synthetic_only`), `allow_real_model_locally` (default false), and catalog entries for real routes.
- **Evaluation summary:** the fields in AC-6. `eval_runs` already records the route and fake flag.

## 8. Interfaces
- No API changes.
- Command line: `make evals EVAL_ARGS="--route direct"` (real mode), and `make route-parity ROUTE=direct` (exists).

## 9. Authorisation and tenancy
- No matrix change.
- The boundary check is tenant-scoped: it reads the call's tenant's `synthetic` flag through a SECURITY DEFINER function (listed in `DEFINER_FUNCTIONS`), cached per process for a minute.

## 10. AI behaviour
- **Agent:** `evidence.screener` as specified, with prompt `evidence.screen@v0`, tier `small`, escalation to `medium`, a $0.03 cost limit per screening and an 800-token output limit.
- **Model input:** totals, cell positions and untrusted account names, all computed by code (ADR-050). Adversarial content is passed as delimited data (ADR-052), and the suite's adversarial cases test that it stays contained.
- **Code still decides:** citations are verified against the stored spreadsheet, figures that don't add up force "needs revision", and agents propose; people decide (ADR-005).

## 11. Integrations
Anthropic's API (direct route), with an evaluation-only key. Synthetic data only.

## 12. Edge cases and failure modes
- **A 429 or capacity refusal:** existing admission handles it, and the run's wait counts toward its limits.
- **A 401 or 403:** the route is left out; the run errors with `provider.auth_failed`, and no fake fallback is used in real mode.
- **A model ID retired by the provider:** the parity check fails, and the catalog must be updated under ADR-074.
- **Someone points the runner at a non-throwaway database:** the runner refuses unless it started the containers itself (existing behaviour, tested).

## 13. Security and privacy
- Only synthetic data reaches the provider. Three layers enforce it (§4.1), and each has a test.
- The key is evaluation-only, spend-capped and never committed. A CI secret comes with staging.
- Lifting the boundary needs a new spec, recorded provider terms (zero retention, no training) as an ADR, and staging (TASK-014).

## 14. Audit trail and evidence integrity
- Boundary refusals are audited (`ai.boundary_refused`: tenant, prompt, route, never content).
- Usage records keep the model ID, prompt version, tokens and cost.

## 15. Observability
Counters: `abacus.ai.boundary_refused` (route, prompt) and the existing usage and admission metrics, which carry the route and model.

## 16. Performance and scale
The suite has 21 cases, 7 of them repeated 5 times. At the spec's $0.03 limit, a full run costs about $1.50 at most, well under the $5 abort.

## 17. UX
None. This is a command-line milestone.

## 18. Test plan
| AC | Type | Notes |
|---|---|---|
| AC-1, AC-4, AC-8 | unit | Settings validation across environments and IDs; secrets hidden |
| AC-2 | unit | The gateway with a stub provider that fails if called |
| AC-3 | integration | Grants: the app role can't write `firms.synthetic` |
| AC-5, AC-6, AC-7 | integration (fake) plus one real run | Fake mode proves the summary fields and the abort; the milestone is one real run, whose report is attached to the task |

## 19. Rollout
Local and `evaluation` only. Nothing deploys.

## 20. Open questions
- **Q1. Which exact model per tier, and their prices?** *Recommendation:*
  - `small` (the screener): Claude Haiku 4.5, `claude-haiku-4-5-20251001`;
  - `medium` (escalation): Claude Sonnet 5.5;
  - `large`: Claude Opus 5.5.

  You confirm the exact pinned IDs and current prices from the provider console before implementation.
- **Q2. Add the per-call synthetic-tenant check (`firms.synthetic`, a migration in identity), not just the settings gate?** *Recommendation: yes.* It's defence in depth: a misconfigured environment still can't send a real firm's data. It touches identity (migration, grant, a definer), which you approve by name.
- **Q3. Allow the real model locally for prompt development, behind `allow_real_model_locally` and still only for synthetic firms, or `evaluation` only?** *Recommendation: allow it locally behind the flag.* Prompt work is slow without it, and the per-call check still applies. Local firms made by sign-up aren't synthetic, so they're refused.
- **Q4. Who holds the key?** *Recommendation:* you create an evaluation-only key with a daily cap (the existing $50 limit) in a separate provider workspace, used only on your machine until staging.
- **Q5. Write `evals/baselines.yaml` (protected) from the first passing real run, for your approval?** *Recommendation: yes.*
- **Q6. If the real model misses a threshold, a follow-up task iterates the prompt (`evidence.screen@v1`) under ADR-074, and thresholds stay as they are?** *Recommendation: yes.*

## 21. Future / explicitly deferred
- **Lifting the boundary for client data:** provider terms recorded, staging, and shadow mode on real traffic (ADR-074).
- The Bedrock route inside our AWS account (SPEC-010), and tier step-down after signed CI runs.
- Further agents with model calls: the engagement agent's planner and briefing (after SPEC-027), and the change analyst.
