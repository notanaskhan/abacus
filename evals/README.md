# Evaluation suites

Every agent has a suite here: `evals/<agent>/suite.yaml`, named by its spec's `evaluation_suite`. The suites are SPEC-005's, built in TASK-020. Thresholds live in them, so they are protected (ADR-079); D5 adds them to the protected paths.

## Running

```
make evals                                               # the screener's full suite
make evals EVAL_ARGS="--subset fast"                     # its fast subset (the PR gate, 020b)
make evals EVAL_ARGS="--agent evidence.screener --tier small --out backend/.evals"
```

The runner (`python -m abacus_tools.evals`) works like this:
- **Validate:** it checks the suite before any model call: graders and metrics come from the registries, the dangerous error has its own threshold, and every declared category is covered.
- **Set up:** it starts throwaway containers (`abacus_tools.stack`).
- **Run each case:**
  - it seeds a retrieval of a synthetic trial balance carrying the case's mutation (`abacus_tools.evals.cases`);
  - it runs the real retrieval pipeline and the screener through the gateway, with the tier pinned by `ai_gateway.evaluation`;
  - it grades the attempt, repeating key cases.
- **Gate:** it computes the metrics, calibration and the gate.
- **Record:** it stores the run in that database's `eval_runs`, writes a JSON summary, and exits 0 only if the run passed.

## Fake and real runs

- **Fake runs:** there is no model provider yet (TASK-014), so runs use the fake model with each case's `fake_answer`. A fake run checks the code: routing, citation verification, containment, calibration maths and the gate. It never measures a model, and never makes a cheaper tier eligible.
- **Eligibility:** the gateway steps down to a `cheaper_tiers` entry only when `eval_eligible` finds a passing, non-fake run for that agent, tier, model and prompt version (SPEC-005 AC-13).
- **Publishing:** `python -m abacus_tools.evals.publish SUMMARY.json --database-url …` loads a summary into an environment's store; the deploy pipeline will run it (TASK-014).

## A suite

A suite declares:
- `covers`: failure-taxonomy and adversarial codes (`docs/product/failure-taxonomy.md`);
- `cases`, each with:
  - `id` and `mutation`;
  - `categories`;
  - `expected` (`stage: screened` with an `action`, or `failed_validation`/`failed` when code catches it first);
  - `fake_answer`;
  - `key` (repeated) and `fast` (in the fast subset);
- `graders` and `thresholds`, including `dangerous_error`;
- `repeats` and `required_pass_rate`;
- `calibration_tolerance` (ECE);
- `cost_limit_usd`.

A run stops with `aborted_cost` before a case would pass the cost limit. The $50 daily limit is the evaluation provider key's own spend limit (D4).

Cost per case is compared with `evals/baselines.yaml`: at most 10% over is allowed. That file is protected, and is added with the first real-model runs.
