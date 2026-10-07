---
id: SPEC-005
title: Evaluation runner, graders and calibration
status: draft
owner: founder
risk_zone: amber
related_adrs: [ADR-076, ADR-081, ADR-082, ADR-070, ADR-055, ADR-047, ADR-068, ADR-072, ADR-073, ADR-083, ADR-085, ADR-019]
related_specs: [SPEC-001, SPEC-003, SPEC-004]
created: 2026-10-07
updated: 2026-10-07
---

> **Instructions for coding agents**
> - Implement only what this spec describes. Anything not listed here is out of scope.
> - If anything is ambiguous or contradicts an ADR, **stop** and add it to *Open questions*. Do not guess.
> - Every test must reference the acceptance criterion (AC-n) it proves.
> - This spec must be `approved` with no open questions before implementation starts.

## 1. Summary
An evaluation runner measures each agent against its evaluation suite. It runs real, pinned models through the AI gateway in evaluation mode (ADR-076), grades every case, measures how well confidence predicts correctness, and decides pass or fail against thresholds weighted toward the agent's dangerous error (ADR-081). Results are stored as evaluation runs. Other things depend on a passing run:
- a prompt, model or tier change (ADR-082);
- a cheaper tier an agent may step down to (`cheaper_tiers`, ADR-072);
- a fallback model (ADR-073);
- later, a firm rule (ADR-068).

This is the Trust-layer primitive "evaluation runner, graders and calibration tooling" of Phase 1 §5.3. The infrastructure is built in full now; cases grow from use (build plan §2).

## 2. Problem and context
Agents are declared with an `evaluation_suite` (ADR-047), and `evals/screening` exists. But it is a pytest file run against `FakeModel` that writes a JSON report to a gitignored folder.
- **No pass or fail:** nothing decides pass or fail, measures calibration, records results anyone can trust, or gates a change.
- **Unenforced ADRs:** ADR-081 (graders, thresholds on the dangerous error, calibration, repeated key cases) and ADR-082 (a fast subset on PRs, the full suite nightly and before rollouts) are not enforced anywhere.
- **Unrunnable gates:** ADR-070 (a cost-per-case regression gate) and ADR-072 and ADR-073 (cheaper tiers and fallbacks only after the suite passes) refer to an evaluation result that can't be produced yet.
- **Phase 2 depends on it:** the exit criterion is "evaluation suites for classifier, matcher, screener and support finder at agreed thresholds".

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Engineer or coding agent | Writes suites, cases and graders; runs evaluations locally (`make evals`) |
| CI | Runs the fast subset on path-triggered PRs (stage 3) and full suites nightly (stage 5) |
| Founder (platform owner) | Sets thresholds and cost limits (protected); approves baseline changes |
| Gateway and agent runtime | Read evaluation results to allow a cheaper tier or fallback model |
| Manager (later, ADR-068) | Activates a firm rule only with a passing evaluation run ID |

## 4. Goals and non-goals
**Goals**
- **One runner** (`abacus_tools.evals`) runs any agent's suite: each case through the real agent code path and the AI gateway, against a chosen model and tier (or `FakeModel` for its own tests), with key cases repeated N times.
- **Suites declare what ADR-081 requires** in a protected, versioned file per agent: cases, graders, thresholds (including the dangerous-error metric), repeat counts, and the per-run cost limit.
- **Graders, deterministic first:** exact checks on structured output; rule-based checks such as failure-taxonomy labels, citation verification and untrusted-text containment; model graders only where the suite declares one, through the gateway, with a pinned judge (Q3).
- **Calibration:** reliability per confidence band, the expected calibration error, and a recommended confidence-routing threshold, compared with the spec's `confidence_routing.below`.
- **The gate:** a run passes only if every threshold holds, calibration is within its tolerance, and cost per case is within the ADR-070 baseline.
- **Stored runs:** results are evaluation runs, immutable and referenceable by ID, with per-case outcomes. Model and prompt versions, tier and route are recorded.
- **Eligibility from runs:** `cheaper_tiers` entries and fallback models are allowed only with a passing run on that tier or model for the current prompt version.
- **CI:** the fast subset on PRs touching prompts, specs, tools, context builders or the gateway (ADR-082 path filters), and the full suites nightly.
- **Cost:** a hard cost ceiling per run and per day for real-model evaluations, and cost per case recorded and compared with a baseline (ADR-070).

**Non-goals**
- **The learning loop:** turning corrections into examples, candidate firm rules or evaluation cases (ADR-068). This spec only lets a later spec reference a passing run.
- **Production drift monitoring** (ADR-082's acceptance and override rates): it needs real use, and comes with increment 11 or an operations spec.
- **Consented or firm production cases** and their restricted storage (ADR-081): the storage interface is defined, and the cases arrive with design partners (Phase 0 §4.4).
- **Human sampling workflows** for judge calibration: the data model allows human labels, and the UI is deferred.
- **A real model provider:** that's TASK-014 or the provider spec. Until then, suites run against `FakeModel` and the gate machinery is proven with it.
- **Suites for agents that don't exist yet** (classifier, matcher, support finder). Each comes with its agent.

## 5. User stories and acceptance criteria
### Story 1: As an engineer I can run an agent's suite and get a trustworthy result
- **AC-1** Given an agent with a declared suite, when `make evals AGENT=evidence.screener` runs, then the runner checks that every one of the suite's cases runs through the agent's real code path and the AI gateway in evaluation mode, against the pinned model for the requested tier. Each key case is repeated its declared number of times. The runner exits 0 only if the run passes.
- **AC-2** Given a suite file, it must declare its cases, graders, thresholds, the dangerous-error metric, repeat counts and cost limit. A suite missing any of them, or naming an unknown grader or metric, is refused before any model call.
- **AC-3** Given the run, then every case gets per-grader outcomes and a pass or fail. Repeated cases are judged on their pass rate against the suite's required rate.
- **AC-4** Given the suite covers an agent whose inputs come from evidence, then it includes at least one case for every failure-taxonomy category and adversarial category the agent's purpose involves (ADR-081, `failure-taxonomy.md`). Uncovered categories make the run invalid, not merely failing.

### Story 2: Grading measures what matters
- **AC-5** Given deterministic graders, then:
  - structured output is compared field by field;
  - failure-taxonomy labels are compared to the case's expected labels;
  - citations are verified by the existing citation verifier;
  - untrusted-text containment and budget adherence are checked.

  All of this runs with no model calls.
- **AC-6** Given a suite that declares a model grader (Q3), then the judge runs through the gateway with its own registered prompt, a pinned model and tier, a budget, and a fixed output schema. Its cost is counted in the run's cost. Its verdicts carry a calibration record against human labels.
- **AC-7** Given the thresholds, then each is a named metric with a minimum, for example `needs_revision_recall >= 0.97` or `ready_precision >= 0.85`. A suite whose only threshold is an accuracy figure is refused: the dangerous error must have its own threshold (ADR-081).

### Story 3: Confidence means something
- **AC-8** Given the run, then calibration is measured: per-band accuracy against stated confidence, and the expected calibration error. The runner reports the confidence threshold that would meet the dangerous-error threshold, next to the spec's current `confidence_routing.below`.
- **AC-9** Given the expected calibration error exceeds the suite's tolerance, or the spec's routing threshold would breach the dangerous-error threshold, then the run fails with reason `calibration`.

### Story 4: Changes are gated
- **AC-10** Given a PR that changes files under the ADR-082 path filters (prompts, agent specs, tools, context builders, `ai_gateway`), then CI stage 3 runs the fast subset of the affected agents' suites. The PR is blocked if the subset fails.
- **AC-11** Given the nightly schedule, then the full suites of every agent run (stage 5). Failures are reported, and the latest result per agent is kept.
- **AC-12** Given cost per case rises by more than the agreed tolerance over the stored baseline (Q5), then the run fails with reason `cost_regression` unless the baseline is updated through the protected baseline file (ADR-070).
- **AC-13** Given an agent spec lists a tier in `cheaper_tiers`, or a route configuration lists a fallback model (ADR-073), then the gateway allows the step-down or failover only if a passing run exists for that agent, tier or model, and prompt version. Otherwise the entry is ignored and logged. A spec or config check flags the entry in CI.

### Story 5: Results are kept and costs bounded
- **AC-14** Given any run, then it is stored as an evaluation run with:
  - its ID, agent, suite version, prompt version, model, tier, route, started and finished times, pass or fail with reasons, and total cost;
  - per-case and per-grader outcomes and cost per case.

  A run is immutable once finished, and is referenceable by ID (ADR-068).
- **AC-15** Given a real-model run, then it stops before spending past the suite's per-run limit and the daily evaluation ceiling (Q6). A stopped run is stored as `aborted_cost`, never as passing.
- **AC-16** Given the runner, then it refuses to run outside local, test, CI or a dedicated evaluation environment (Q4), and never reads a deployed environment's client data. Firm-scoped cases stay within their firm (ADR-081).

## 6. Behaviour and flows
**Happy path (a PR that edits the screener's prompt)**
1. CI stage 3 sees `prompts/evidence.screen/**` changed. The agent is `evidence.screener`, and its fast subset is selected.
2. The runner loads `evals/screening/suite.yaml`, validates it (AC-2, AC-4, AC-7) and checks the cost limit.
3. For each case, it seeds the synthetic world (SPEC-001), runs retrieval and the screener through the gateway in evaluation mode with the pinned model and tier, and repeats key cases.
4. Graders score each case, and calibration and cost per case are computed.
5. The gate compares the results with the thresholds, the calibration tolerance and the cost baseline. The run is stored (AC-14), and the job passes or fails with reasons.

**Alternate paths**
- **No provider configured:** the runner uses `FakeModel` with the suite's recorded responses. The run is marked `fake` and never counts as eligibility for a tier or model (AC-13).
- **A cheaper tier:** `make evals AGENT=… TIER=small`. A passing run on the cheaper tier with the current prompt version makes that `cheaper_tiers` entry effective.
- **Cost ceiling reached:** the run stops with `aborted_cost` (AC-15).

**State transitions** (an evaluation run)
| From | Event | To | Who can trigger |
|---|---|---|---|
| (none) | start | running | engineer, CI |
| running | all cases graded | passed or failed | runner |
| running | cost limit reached | aborted_cost | runner |
| running | error | errored | runner |

## 7. Domain and data changes
- **Suite file** per agent (`evals/<agent>/suite.yaml`, protected because thresholds are in it, per ADR-079):
  - cases (inline, or references to synthetic seeds and flaws);
  - graders;
  - thresholds;
  - `dangerous_error` metric;
  - repeat counts;
  - the fast-subset selector;
  - calibration tolerance;
  - per-run cost limit;
  - required pass rate for repeated cases.
- **Evaluation runs store** (Q2): runs and case results, immutable once finished. In Phase 1 it holds synthetic runs only. Firm-scoped results get tenant scoping when consented cases arrive.
- **Cost baseline** per agent and suite, in a protected file updated only by approval (ADR-070).
- **Gateway evaluation mode:** usage records carry `purpose = evaluation` and the run ID, so evaluation spend is attributable and never counted as a firm's spend.
- **Agent specs:** no new required fields. `cheaper_tiers` gains its runtime check (AC-13).
- **Glossary:** add "evaluation run", "grader", "calibration" and "dangerous error" if missing (protected; needs the founder).

## 8. Interfaces
| Interface | Purpose |
|---|---|
| `make evals [AGENT=…] [TIER=…] [SUBSET=fast\|full]` | Run suites locally and in CI |
| `abacus_tools.evals.run(agent, tier, subset) -> EvalRun` | The runner (tooling; never imported by `abacus`) |
| `abacus_tools.evals.graders` | Deterministic and rule graders, plus the model-grader wrapper |
| `ai_gateway.eligible(agent_id, tier or model, prompt_version) -> bool` | Reads the latest passing run (AC-13) |
| CI jobs | Stage 3 `evals-fast` (path-filtered); stage 5 `evals-full` (nightly) |

No HTTP API. A results page is deferred (§21).

## 9. Authorisation and tenancy
- **Tenant scoping:** Phase 1 runs use synthetic tenants only. When firm-scoped cases arrive, their runs and results are stored per firm and never pooled (ADR-081). The store design must allow that without migrating existing rows (Q2).
- **Who can do what:** evaluations are platform tooling, not a product action, so there are no matrix actions. Thresholds, baselines and cost limits are protected files.
- **Eligibility reads** (AC-13) are platform data: they hold no client data and are not tenant-scoped.
- **Client-side access:** none.

## 10. AI behaviour
- **Agents under test:** real agent code through the gateway (ADR-019) in evaluation mode, with the same prompts, schemas, limits and context builders as production.
- **Model graders (Q3):** a registered judge prompt (`id@vN`), a pinned model and tier, a budget, and a fixed output schema. The judge's own calibration against human labels is recorded, and a judge without a calibration record can't gate.
- **Cost:** per-case costs are recorded (ADR-070), plus per-run and daily ceilings (Q6).
- **Untrusted inputs:** adversarial cases (prompt injection and the rest) are required (AC-4).

## 11. Integrations
- **The model provider:** real runs need it (TASK-014 or the provider spec). Until then, `FakeModel`.
- **CI:** GitHub Actions stages 3 and 5 (ADR-083), using a provider secret scoped to evaluations only (Q4).

## 12. Edge cases and failure modes
- **Non-determinism:** key cases repeat and are judged on pass rate (ADR-081). Temperature and other sampling settings are pinned per suite.
- **Provider errors during a run:** retried per gateway policy. If too many cases error, the run is `errored`, never `passed`.
- **A changed suite:** results record the suite version. Eligibility needs a pass on the current prompt version.
- **Fake runs:** marked `fake`, never eligibility.
- **Cost overrun mid-run:** `aborted_cost`.
- **Flaky graders:** a grader that errors makes the case fail with reason `grader_error`, never pass.

## 13. Security and privacy
- **Data classification:**
  - suites and runs hold synthetic data (internal);
  - consented production cases are restricted, kept outside the repository (ADR-081), and only referenced.
- **PII:** none in Phase 1.
- **Secrets:** a dedicated evaluation provider key with spend limits, in CI secrets only (Q4).
- **Threats:**
  - leaking client data into evaluation logs (mitigated: synthetic only; logs carry IDs and metrics);
  - unbounded spend (mitigated: per-run and daily ceilings);
  - gaming thresholds (mitigated: thresholds are protected files).

## 14. Audit trail and evidence integrity
Evaluation runs are immutable once finished and keep their full inputs (model, prompt version, suite version, seeds). The audit trail of product actions isn't involved, because evaluations aren't product actions. A later firm-rule activation records the run ID (ADR-068).

## 15. Observability
- **Logs:** `eval.run.started` and `eval.run.finished` (agent, tier, model, outcome, cost), and `eval.case.failed` (case ID, grader, reason; never client text).
- **Metrics:** pass rate per agent and threshold, calibration error, cost per case, and evaluation spend per day.
- **CI summaries:** each run is linked from the job.

## 16. Performance and scale
- **Fast subset:** under 5 minutes on PRs (stage 3).
- **Full suite:** under 30 minutes nightly per agent at Phase 1 sizes.
- **Concurrency:** cases run concurrently up to a provider-friendly limit, the same admission control as SPEC-003.

## 17. UX
No UI. The results are a CI summary and the stored runs. A results page is deferred (§21).

## 18. Test plan
| AC | Test type | Description |
|---|---|---|
| AC-1–AC-3 | integration (FakeModel) | The runner runs the screener's suite end to end; repeats; exit code |
| AC-2, AC-4, AC-7 | unit | Suite validation: missing parts, unknown graders, uncovered categories, accuracy-only thresholds |
| AC-5 | unit | Each deterministic grader against fixed outputs |
| AC-6 | unit + integration | Model grader through the gateway with a fake judge; calibration record required |
| AC-8, AC-9 | unit | Calibration maths on fixed data; the routing-threshold recommendation; calibration failure |
| AC-10, AC-11 | CI config test | Path filters select the right agents; the nightly job exists |
| AC-12 | unit | Cost regression against the baseline |
| AC-13 | unit + integration | The gateway ignores an ineligible cheaper tier; a passing non-fake run makes it eligible |
| AC-14 | integration | The run is stored, immutable and readable by ID |
| AC-15 | unit | Ceilings stop a run with `aborted_cost` |
| AC-16 | unit | The environment guard |

## 19. Rollout
- **First, with `FakeModel`:** the runner, graders, calibration, gate, store, `make evals` and the CI jobs, which prove the machinery.
- **Then, with a provider (TASK-014):** the first real runs, which set baselines and turn the gates on.
- **No flag:** eligibility (AC-13) is fail-closed from day one. With no passing real run, no cheaper tier or fallback is used. Today that means none, which is the current behaviour.

## 20. Open questions
- [ ] **Q1: suite format.** A declarative YAML suite per agent (cases, graders, thresholds), with cases as Python factories over the synthetic generator? Or suites written as pytest files, as `evals/screening` is today? *Recommendation:* a YAML suite file (protected, because thresholds live there), with cases referencing generator seeds and flaws, and graders by registered name. Keep pytest only as the runner's own test harness. The existing screening pytest cases migrate into the suite.
- [ ] **Q2: where results live.** Postgres tables, as platform tables like the slot ledger (no tenant, no app privileges, written by tooling), or JSON artefacts in object storage? *Recommendation:* Postgres `eval_runs` and `eval_case_results`, insert-only. A run row is finalised once, then immutable, and has a nullable `tenant_id` for later firm-scoped cases. The runner writes as a dedicated role, and the gateway reads eligibility through a SECURITY DEFINER function. CI also uploads a JSON summary as a build artefact.
- [ ] **Q3: model graders now?** ADR-081 allows a pinned, human-calibrated judge for subjective qualities. *Recommendation:* build the model-grader wrapper and its calibration record now. The screener's suite uses deterministic and rule graders only, since its outputs are structured, so no judge gates anything until a suite needs one.
- [ ] **Q4: where real-model runs happen, and with which key.** *Recommendation:* in CI stage 3 and stage 5 jobs, and in a local `evaluation` environment. Use a dedicated provider key with a provider-side spend limit, stored only as a CI secret. Never in staging or production processes.
- [ ] **Q5: the cost-regression tolerance (ADR-070).** *Recommendation:* fail when the median cost per case rises more than 10% over the baseline. The baseline is updated only by editing the protected baseline file in the same PR, with a reason.
- [ ] **Q6: cost ceilings.** *Recommendation:* a per-run limit declared per suite (screener: $5), and a daily evaluation ceiling of $50 across all runs (a setting), until a cost model exists.
- [ ] **Q7: the fast subset.** *Recommendation:* the suite marks which cases are fast. It must include at least one case per dangerous-error class, and the subset aims for under 5 minutes and under $1.
- [ ] **Q8: initial thresholds for the screener.** *Recommendation:* `needs_revision_recall >= 0.97` (the dangerous error is calling flawed evidence ready), `ready_precision >= 0.85`, adversarial containment 1.00, citation verification 1.00, and expected calibration error <= 0.10. Repeat key cases 5 times, with a 0.8 pass rate. Revisit after the first real baselines.

## 21. Future / explicitly deferred
- **The learning loop:** corrections become cases and firm rules (ADR-068).
- **Production drift monitoring:** override and acceptance rates (ADR-082).
- **Consented and firm-scoped cases**, with restricted storage.
- **Human sampling** and labelling UI for judge calibration.
- **A results page** in the SPA.
- **Suites for the classifier, matcher and support finder**, with their agents.
