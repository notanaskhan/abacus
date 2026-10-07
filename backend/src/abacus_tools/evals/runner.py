"""The evaluation runner (SPEC-005 AC-1 to AC-3, AC-14 to AC-16; TASK-020 design §3, D2 to D4).

    python -m abacus_tools.evals --agent evidence.screener [--tier small] [--subset fast]

Runs an agent's suite through its real code: for each case it seeds a synthetic retrieval whose
trial balance carries the case's mutation, runs the retrieval pipeline and the screener through
the gateway (evaluation mode pins the tier and never steps down), grades the attempt, and repeats
key cases. It runs on a throwaway stack (`abacus_tools.stack`): containers, a fresh database,
never a deployed environment's data (AC-16). Without a model provider it uses the fake model with
each case's recorded answer, and the run is marked fake: it proves the code paths, never a
model's quality, and never makes a tier eligible (AC-13). Results are stored in the throwaway
database's evaluation tables and written as a JSON summary (D3), signed when CI's key is set;
`publish` loads a summary into another store. The run stops with `aborted_cost` before a case
would pass its cost limit (D4), and an exception finishes it as `errored`.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

import asyncpg
import yaml

from abacus.ai_gateway import MODELS, FakeModel, ModelRequest, Tier, configure_provider, evaluation
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
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
from abacus_tools.evals.cases import MUTATION_CATEGORIES, MUTATIONS
from abacus_tools.evals.graders import GRADERS
from abacus_tools.evals.metrics import METRICS, Attempt
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import Case, Suite, load, validate
from abacus_tools.evals.summary import Summary, sign
from abacus_tools.evals.verdict import Verdict, judge
from abacus_tools.stack import (
    TRIAL_BALANCE_SEED,
    Seeded,
    Stack,
    assert_engines_on,
    connect,
    connect_db,
    is_loopback,
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
# Settings that point the platform somewhere: each must be this machine, or the configured
# evaluation database (AC-16).
_DESTINATIONS = (
    "ABACUS_DATABASE_URL",
    "ABACUS_MIGRATIONS_DATABASE_URL",
    "ABACUS_RELAY_DATABASE_URL",
    "ABACUS_IDENTITY_DATABASE_URL",
    "ABACUS_S3_ENDPOINT_URL",
    "ABACUS_TEMPORAL_TARGET",
)
EVALUATION_DATABASE_ENV = "ABACUS_EVALUATION_DATABASE_URL"
_log = get_logger(__name__)
_meter = meter(__name__)
_runs = _meter.create_counter("abacus.eval.runs", description="Evaluation runs by outcome")
_failed_cases = _meter.create_counter(
    "abacus.eval.case_failures", description="Evaluation case attempts that failed, by reason"
)


class RefusedEnvironment(RuntimeError):
    """Evaluations run only locally, in tests or in the evaluation environment, against this
    machine (Q4, AC-16)."""


def guard() -> None:
    environment = settings().environment
    if environment not in SYNTHETIC_ENVIRONMENTS:
        raise RefusedEnvironment(f"evaluations don't run in {environment!r}")
    allowed = os.environ.get(EVALUATION_DATABASE_ENV)
    for name in _DESTINATIONS:
        value = os.environ.get(name)
        if value and not is_loopback(value) and value != allowed:
            raise RefusedEnvironment(f"{name} points away from this machine")


def suite_for(agent: str) -> Suite:
    suite = load(REPO / spec(agent).evaluation_suite / "suite.yaml")
    validate(
        suite,
        graders=frozenset(GRADERS),
        metrics=frozenset(METRICS),
        mutations=MUTATION_CATEGORIES,
    )
    return suite


def baseline(agent: str, tier: str) -> Decimal | None:
    if not BASELINES.exists():
        return None
    raw = cast(dict[str, dict[str, object]], yaml.safe_load(BASELINES.read_text()) or {})
    value = raw.get(agent, {}).get(tier)
    return Decimal(str(value)) if value is not None else None


async def _new_item(world: Seeded, superuser: str) -> uuid.UUID:
    conn = await connect_db(superuser)
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


async def _spent(superuser: str, run_id: uuid.UUID) -> tuple[Decimal, set[str]]:
    conn = await connect_db(superuser)
    try:
        cost = await conn.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_records WHERE agent_run_id = $1", run_id
        )
        models = await conn.fetch(
            "SELECT DISTINCT model FROM usage_records WHERE agent_run_id = $1", run_id
        )
    finally:
        await conn.close()
    return Decimal(str(cost)), {str(m["model"]) for m in models}


async def _result(superuser: str, run_id: uuid.UUID) -> tuple[str, str, list[dict[str, object]]]:
    conn = await connect_db(superuser)
    try:
        row = await conn.fetchrow(
            "SELECT action, created_by_kind, citations FROM screening_results "
            "WHERE agent_run_id = $1",
            run_id,
        )
    finally:
        await conn.close()
    if row is None:
        raise RuntimeError("the screener recorded no result")
    citations = row["citations"]
    parsed = json.loads(citations) if isinstance(citations, str) else citations
    return str(row["action"]), str(row["created_by_kind"]), cast(list[dict[str, object]], parsed)


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

    run_id: uuid.UUID | None = None
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
            outcome = await screen(await load_agent_context(world.tenant, run_id))
        action, kind, citations = await _result(stack.superuser, run_id)
        cost, models = await _spent(stack.superuser, run_id)
        if outcome.status != "completed" or kind != "agent":
            raise RuntimeError(f"screening ended {outcome.status} by {kind}")
        if models != {MODELS[tier][0]}:
            raise RuntimeError("the screener ran on a model other than the pinned tier's")
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
        # What a failed attempt spent still counts; unreadable, it counts as its whole budget.
        cost = Decimal(0)
        if run_id is not None:
            try:
                cost, _ = await _spent(stack.superuser, run_id)
            except Exception:
                cost = budget
        return Observation(
            case.id,
            attempt,
            "errored",
            cost_usd=cost,
            budget_usd=budget,
            error=type(exc).__name__,
        )
    finally:
        configure_provider(None)


AttemptFn = Callable[[Case, int], Awaitable[Observation]]


async def collect(
    suite: Suite, subset: Subset, budget: Decimal, attempt: AttemptFn
) -> tuple[list[Attempt], bool]:
    """Every case of the subset, key cases `repeats` times, stopping (aborted) before an attempt
    whose budget would take the run past its cost limit (AC-15)."""
    attempts: list[Attempt] = []
    total = Decimal(0)
    for case in suite.subset(subset):
        for n in range(1, (suite.repeats if case.key else 1) + 1):
            if total + budget > suite.cost_limit_usd:
                return attempts, True
            seen = await attempt(case, n)
            total += seen.cost_usd
            attempts.append((case, seen))
    return attempts, False


async def store_start(conn: asyncpg.Connection, run: Summary) -> None:
    await conn.execute(
        "INSERT INTO eval_runs (id, agent_id, suite_version, prompt_version, model, tier, "
        "subset, fake, route, seeds, started_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
        run.id,
        run.agent,
        run.suite_version,
        run.prompt_version,
        run.model,
        run.tier,
        run.subset,
        run.fake,
        run.route,
        json.dumps(run.seeds),
        run.started_at,
    )


async def store_finish(conn: asyncpg.Connection, summary: Summary) -> None:
    """Record the cases, then finish the run (immutable from then on)."""
    for case in summary.cases:
        await conn.execute(
            "INSERT INTO eval_case_results (run_id, case_id, attempt, passed, graders, cost_usd) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            summary.id,
            case.case_id,
            case.attempt,
            case.passed,
            json.dumps([g.model_dump() for g in case.grades]),
            case.cost_usd,
        )
    await conn.execute(
        "UPDATE eval_runs SET status = $2, reasons = $3, metrics = $4, calibration = $5, "
        "total_cost_usd = $6, finished_at = $7 WHERE id = $1",
        summary.id,
        summary.status,
        list(summary.reasons),
        json.dumps(summary.metrics),
        json.dumps(summary.calibration),
        summary.total_cost_usd,
        summary.finished_at,
    )


def summarise(run: Summary, verdict: Verdict) -> Summary:
    return sign(
        Summary.model_validate(
            {
                **run.model_dump(),
                "status": verdict.status,
                "reasons": verdict.reasons,
                "metrics": verdict.metrics,
                "calibration": json.loads(json.dumps(verdict.calibration)),
                "total_cost_usd": verdict.total_cost_usd,
                "median_case_cost_usd": verdict.median_case_cost_usd,
                "finished_at": datetime.now(UTC),
                "cases": verdict.case_rows,
            }
        )
    )


def _errored(run: Summary, error: BaseException) -> Summary:
    return sign(
        Summary.model_validate(
            {
                **run.model_dump(),
                "status": "errored",
                "reasons": [f"error:{type(error).__name__}"],
                "finished_at": datetime.now(UTC),
            }
        )
    )


async def evaluate_on(
    stack: Stack, suite: Suite, subset: Subset, tier: Tier, out: Path
) -> Summary:
    """Run `suite` on a throwaway stack that's already up; store and write its summary."""
    await connect(stack)
    settings.cache_clear()
    assert_engines_on(stack)
    directory = Path(os.environ["ABACUS_FAKE_CONNECTOR_DIR"])
    world = await seed(stack.superuser)
    run = Summary(
        id=uuid.uuid4(),
        agent=suite.agent,
        suite_version=suite.version,
        prompt_version=spec(suite.agent).prompt,
        model=MODELS[tier][0],
        tier=tier,
        subset=subset,
        fake=True,  # no model provider exists yet (TASK-014): fake runs only
        route=settings().model_provider,
        seeds={"trial_balance": TRIAL_BALANCE_SEED},
        sampling=suite.sampling,
        status="errored",  # until finished
        reasons=(),
        metrics={},
        calibration={},
        total_cost_usd=Decimal(0),
        median_case_cost_usd=Decimal(0),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        cases=(),
    )
    conn = await connect_db(stack.superuser)
    try:
        await store_start(conn, run)
    finally:
        await conn.close()
    _log.info("eval.run.started", agent=suite.agent, tier=tier, model=run.model, subset=subset)
    budget = spec(suite.agent).limits.max_cost_usd
    routing = spec(suite.agent).confidence_routing
    try:

        async def attempt(case: Case, n: int) -> Observation:
            return await _attempt(case, n, world, stack, directory, tier)

        attempts, aborted = await collect(suite, subset, budget, attempt)
        verdict = judge(
            suite,
            attempts,
            fake=run.fake,
            aborted=aborted,
            baseline=baseline(suite.agent, tier),
            current_below=float(routing.below),
            route=routing.route,
        )
        summary = summarise(run, verdict)
    except Exception as exc:
        summary = _errored(run, exc)
    conn = await connect_db(stack.superuser)
    try:
        await store_finish(conn, summary)
    finally:
        await conn.close()
    _report(summary)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{suite.agent}-{summary.id}.json").write_text(summary.model_dump_json(indent=2))
    return summary


def _report(summary: Summary) -> None:
    for case in summary.cases:
        for g in case.grades:
            if not g.passed:
                _log.info(
                    "eval.case.failed",
                    case_id=case.case_id,
                    attempt=case.attempt,
                    grader=g.grader,
                    reason=g.reason,
                )
                _failed_cases.add(1, {"reason": g.grader, "outcome": "failed"})
    _runs.add(1, {"outcome": summary.status, "model": summary.model})
    _log.info(
        "eval.run.finished",
        agent=summary.agent,
        tier=summary.tier,
        model=summary.model,
        outcome=summary.status,
        reasons=list(summary.reasons),
        cost_usd=str(summary.total_cost_usd),
    )


def run(
    agent: str,
    tier: Tier | None,
    subset: Subset,
    out: Path,
    *,
    suites: Sequence[Suite] | None = None,
) -> list[Summary]:
    """Run `agent`'s suite (validated before any model call), or each of `suites` (tests), on one
    throwaway stack, and return the summaries."""
    guard()
    chosen: Tier = tier or spec(agent).tier
    todo = list(suites) if suites is not None else [suite_for(agent)]
    results: list[Summary] = []

    async def record(stack: Stack) -> None:
        for suite in todo:
            results.append(await evaluate_on(stack, suite, subset, chosen, out))

    run_with_stack(record)
    return results


__all__ = [
    "RefusedEnvironment",
    "baseline",
    "collect",
    "evaluate_on",
    "guard",
    "judge",
    "run",
    "store_finish",
    "store_start",
    "suite_for",
]
