"""The evaluation runner (SPEC-005 AC-1 to AC-3, AC-14 to AC-16; TASK-020 design §3, D2 to D4).

    python -m abacus_tools.evals --agent evidence.screener [--tier small] [--subset fast]

Runs an agent's suite through its real code: for each case it seeds a synthetic retrieval
whose trial balance carries the case's mutation, runs the retrieval pipeline and the screener
through the gateway (evaluation mode pins the tier), grades the attempt, and repeats key cases.
It runs on a throwaway stack (`abacus_tools.stack`): containers, a fresh database, never a
deployed environment's data (AC-16). Without a model provider it uses the fake model with each
case's recorded answer, and the run is marked fake: it proves the code paths, never a model's
quality, and never makes a tier eligible (AC-13). Results are stored in the throwaway database's
evaluation tables and written as a JSON summary (D3); `publish` loads a summary into another
store. The run stops with `aborted_cost` before a case would pass its cost limit (D4).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Literal, cast

import asyncpg
import yaml

from abacus.ai_gateway import MODELS, FakeModel, ModelRequest, Tier, configure_provider, evaluation
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.db import configure_engine
from abacus.modules.agents.api import (
    SCREEN_PROMPT,
    SCREENER,
    create_screening_run,
    load_agent_context,
    screen,
    screening_responder,
    spec,
)
from abacus.modules.connections.api import (
    RunFailed,
    load_system_context,
    run_pipeline,
    start_retrieval,
)
from abacus_tools.evals.calibration import calibrate
from abacus_tools.evals.cases import MUTATIONS
from abacus_tools.evals.gate import reasons
from abacus_tools.evals.graders import GRADERS, grade
from abacus_tools.evals.metrics import METRICS, Attempt
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import Case, Suite, load, validate
from abacus_tools.stack import (
    Seeded,
    Stack,
    connect,
    period_of,
    run_with_stack,
    seed,
    trial_balance,
)
from abacus_tools.synthetic.connector_fixtures import trial_balance_document, write_raw

REPO = Path(__file__).resolve().parents[4]
BASELINES = REPO / "evals" / "baselines.yaml"
UNTRUSTED_NAMES = '<untrusted name="account_names">'
Subset = Literal["fast", "full"]


class RefusedEnvironment(RuntimeError):
    """Evaluations run only locally, in tests, in CI or in the evaluation environment (Q4)."""


def guard() -> None:
    if settings().environment not in SYNTHETIC_ENVIRONMENTS and os.environ.get("CI") != "true":
        raise RefusedEnvironment(f"evaluations don't run in {settings().environment!r}")


def suite_for(agent: str) -> Suite:
    path = REPO / spec(agent).evaluation_suite / "suite.yaml"
    suite = load(path)
    validate(
        suite,
        graders=frozenset(GRADERS),
        metrics=frozenset(METRICS),
        mutations=frozenset(MUTATIONS),
    )
    return suite


def _baseline(agent: str, tier: str) -> Decimal | None:
    if not BASELINES.exists():
        return None
    raw = cast(dict[str, dict[str, object]], yaml.safe_load(BASELINES.read_text()) or {})
    value = raw.get(agent, {}).get(tier)
    return Decimal(str(value)) if value is not None else None


async def _new_item(world: Seeded, superuser: str) -> uuid.UUID:
    conn = await asyncpg.connect(superuser)
    try:
        list_id = await conn.fetchval(
            "SELECT id FROM request_lists WHERE tenant_id = $1 AND engagement_id = $2",
            world.tenant,
            world.engagement,
        )
        return cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by) VALUES ($1, $2, $3, 'Trial balance', "
                "'general', $4) RETURNING id",
                world.tenant,
                world.engagement,
                list_id,
                world.user,
            ),
        )
    finally:
        await conn.close()


async def _screening_row(
    superuser: str, run_id: uuid.UUID
) -> tuple[str, list[dict[str, object]], Decimal]:
    conn = await asyncpg.connect(superuser)
    try:
        row = await conn.fetchrow(
            "SELECT action, citations FROM screening_results WHERE agent_run_id = $1", run_id
        )
        cost = await conn.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_records WHERE agent_run_id = $1", run_id
        )
    finally:
        await conn.close()
    if row is None:
        raise RuntimeError("the screener recorded no result")
    citations = row["citations"]
    parsed = json.loads(citations) if isinstance(citations, str) else citations
    return str(row["action"]), cast(list[dict[str, object]], parsed), Decimal(str(cost))


def _contained(request: ModelRequest) -> bool:
    if UNTRUSTED_NAMES not in request.user:
        return False
    before, inside = request.user.split(UNTRUSTED_NAMES, 1)
    return "</untrusted>" not in before and inside.count("</untrusted>") == 1


async def _attempt(
    case: Case, attempt: int, world: Seeded, stack: Stack, directory: Path, tier: Tier
) -> Observation:
    budget = spec(SCREENER).limits.max_cost_usd
    seen: list[ModelRequest] = []
    answers: list[dict[str, object]] = []

    def responder(request: ModelRequest) -> str:
        seen.append(request)
        answer = cast(dict[str, object], json.loads(screening_responder(request)))
        if case.fake_answer is not None:
            answer["action"] = case.fake_answer.action
            answer["confidence"] = case.fake_answer.confidence
        answers.append(answer)
        return json.dumps(answer)

    configure_provider(FakeModel({SCREEN_PROMPT: responder}))
    try:
        tb = trial_balance()
        period = period_of(tb)
        document = trial_balance_document(tb, period_start=period.start, entity_name="Example")
        mutated = MUTATIONS[case.mutation](document)
        content = mutated if isinstance(mutated, bytes) else json.dumps(mutated).encode()
        write_raw(directory, world.connection, period, content)
        item = await _new_item(world, stack.superuser)
        started = await start_retrieval(
            world.context(), engagement_id=world.engagement, request_item_id=item, period=period
        )
        try:
            result = await run_pipeline(await load_system_context(world.tenant, started.run_id))
        except RunFailed as failed:
            return Observation(
                case.id,
                attempt,
                "failed_validation" if failed.status == "failed_validation" else "failed",
                budget_usd=budget,
            )
        run_id = await create_screening_run(
            world.tenant, result.evidence_version_id, uuid.uuid4(), world.user
        )
        if run_id is None:
            raise RuntimeError("no screening run was created")
        with evaluation(tier):
            await screen(await load_agent_context(world.tenant, run_id))
        action, citations, cost = await _screening_row(stack.superuser, run_id)
        answer = answers[-1] if answers else {}
        return Observation(
            case.id,
            attempt,
            "screened",
            action=action,
            model_action=cast(str | None, answer.get("action")),
            confidence=float(cast(float, answer["confidence"]))
            if "confidence" in answer
            else None,
            citations_verified=bool(citations)
            and all(c.get("verified") is True for c in citations),
            contained=bool(seen) and all(_contained(r) for r in seen),
            cost_usd=cost,
            budget_usd=budget,
        )
    except Exception as exc:
        return Observation(
            case.id, attempt, "errored", budget_usd=budget, error=type(exc).__name__
        )
    finally:
        configure_provider(None)


async def _store_start(superuser: str, run: dict[str, object]) -> None:
    conn = await asyncpg.connect(superuser)
    try:
        await conn.execute(
            "INSERT INTO eval_runs (id, agent_id, suite_version, prompt_version, model, tier, "
            "subset, fake) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            run["id"],
            run["agent"],
            run["suite_version"],
            run["prompt_version"],
            run["model"],
            run["tier"],
            run["subset"],
            run["fake"],
        )
    finally:
        await conn.close()


async def store_finish(conn: asyncpg.Connection, summary: dict[str, object]) -> None:
    """Record the cases and finish the run (immutable from then on)."""
    for case in cast(list[dict[str, object]], summary["cases"]):
        await conn.execute(
            "INSERT INTO eval_case_results (run_id, case_id, attempt, passed, graders, cost_usd) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            uuid.UUID(str(summary["id"])),
            case["case_id"],
            case["attempt"],
            case["passed"],
            json.dumps(case["grades"]),
            Decimal(str(case["cost_usd"])),
        )
    await conn.execute(
        "UPDATE eval_runs SET status = $2, reasons = $3, metrics = $4, calibration = $5, "
        "total_cost_usd = $6, finished_at = clock_timestamp() WHERE id = $1",
        uuid.UUID(str(summary["id"])),
        summary["status"],
        summary["reasons"],
        json.dumps(summary["metrics"]),
        json.dumps(summary["calibration"]),
        Decimal(str(summary["total_cost_usd"])),
    )


async def _evaluate(
    suite: Suite, subset: Subset, tier: Tier, stack: Stack, out: Path
) -> dict[str, object]:
    await connect(stack)
    settings.cache_clear()
    directory = Path(os.environ["ABACUS_FAKE_CONNECTOR_DIR"])
    world = await seed(stack.superuser)
    model = MODELS[tier][0]
    run: dict[str, object] = {
        "id": uuid.uuid4(),
        "agent": suite.agent,
        "suite_version": suite.version,
        "prompt_version": SCREEN_PROMPT,
        "model": model,
        "tier": tier,
        "subset": subset,
        "fake": True,  # no model provider exists yet (TASK-014): fake runs only
    }
    await _store_start(stack.superuser, run)
    attempts: list[Attempt] = []
    total = Decimal(0)
    status = "passed"
    budget = spec(SCREENER).limits.max_cost_usd
    for case in suite.subset(subset):
        for attempt in range(1, (suite.repeats if case.key else 1) + 1):
            if total + budget > suite.cost_limit_usd:
                status = "aborted_cost"
                break
            # Fresh connections per attempt: retrieval's `insert_run` fails on a pooled connection
            # once Postgres switches its prepared ON CONFLICT statement to a generic plan (the
            # partial-index predicate is bound as parameters). A product bug, reported in
            # TASK-020; remove this when `connections.repository.insert_run` is fixed.
            configure_engine(stack.app_url)
            seen = await _attempt(case, attempt, world, stack, directory, tier)
            total += seen.cost_usd
            attempts.append((case, seen))
        if status == "aborted_cost":
            break
    case_rows: list[dict[str, object]] = []
    by_case: dict[str, list[bool]] = {}
    for case, seen in attempts:
        grades = grade(suite.graders, case, seen)
        passed = all(g.passed for g in grades)
        by_case.setdefault(case.id, []).append(passed)
        case_rows.append(
            {
                "case_id": case.id,
                "attempt": seen.attempt,
                "passed": passed,
                "grades": [asdict(g) for g in grades],
                "cost_usd": str(seen.cost_usd),
                "stage": seen.stage,
                "action": seen.action,
            }
        )
    metrics = {name: METRICS[name](attempts) for name in METRICS}
    dangerous = next(t.minimum for t in suite.thresholds if t.metric == suite.dangerous_error)
    calibration = calibrate(
        attempts,
        current_below=float(spec(SCREENER).confidence_routing.below),
        dangerous_minimum=dangerous,
    )
    failed_cases = [
        case_id
        for case_id, results in by_case.items()
        if sum(results) / len(results) < suite.required_pass_rate
    ]
    found = reasons(
        suite,
        metrics,
        calibration,
        [s.cost_usd for _, s in attempts if s.stage == "screened"],
        _baseline(suite.agent, tier),
        sum(s.stage == "errored" for _, s in attempts),
    )
    if failed_cases:
        found.append("cases:" + ",".join(failed_cases))
    if status != "aborted_cost":
        status = "passed" if not found else "failed"
    screened_costs = [s.cost_usd for _, s in attempts if s.stage == "screened"]
    summary: dict[str, object] = {
        **{k: str(v) if isinstance(v, uuid.UUID) else v for k, v in run.items()},
        "status": status,
        "reasons": found,
        "metrics": metrics,
        "calibration": asdict(calibration),
        "total_cost_usd": str(total),
        "median_case_cost_usd": str(median(screened_costs)) if screened_costs else "0",
        "finished_at": datetime.now(UTC).isoformat(),
        "cases": case_rows,
    }
    conn = await asyncpg.connect(stack.superuser)
    try:
        await store_finish(conn, summary)
    finally:
        await conn.close()
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{suite.agent}-{summary['id']}.json").write_text(json.dumps(summary, indent=2))
    return summary


def run(agent: str, tier: Tier | None, subset: Subset, out: Path) -> dict[str, object]:
    """Run `agent`'s suite (validated before any model call) and return its summary."""
    guard()
    suite = suite_for(agent)
    chosen: Tier = tier or spec(agent).tier
    result: dict[str, object] = {}

    async def record(stack: Stack) -> None:
        result.update(await _evaluate(suite, subset, chosen, stack, out))

    run_with_stack(record)
    return result


__all__ = ["RefusedEnvironment", "guard", "run", "store_finish", "suite_for"]
