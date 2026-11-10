"""Real runs of `notices.responder` (N-04-T25; N-04 §6; SPEC-026).

    python -m abacus_tools.evals --agent notices.responder --route direct|bedrock [--subset fast]

On a throwaway stack's synthetic firm (the data boundary applies). Each case runs `repeats` times
through the gateway with the spec's own prompts, tiers and budgets: `analyze` with code's facts
and the cited lines as `<untrusted>`, `extract` with the notice's word layer. Every attempt is
graded by `notices_responder.run`, the same code graders as the fake run. Code's own check
(`check_notice_answer`) runs on every analyze answer too: an answer it refuses is graded, and named
in the report, as it would be never shown.

The report says, per mode, whether the run clears it (`clearance`): only on the Bedrock route,
only when every frozen threshold for that mode passes and no attempt errored, its median cost is
within 10 % of the protected baseline (`evals/baselines.yaml`), and for `analyze` only once the
suite's `label_review` is `reviewed` (the CPA label review, DEC-2312). The report is signed with
CI's key (HMAC-SHA256, `ABACUS_EVAL_SIGNING_KEY`). A cleared mode is recorded by a person, from a
signed report, in `evals/notices_responder/clearance.yaml`; the spec's `client_data` turns
`cleared` only when every mode is recorded there (`test_n04t25_clearance.py`). Route parity
within 90 days is `guard_real`'s.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import statistics
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

from pydantic import BaseModel

from abacus.ai_gateway import (
    Attribution,
    ContextBuilder,
    GatewayCall,
    ModelRequest,
    NotAdmitted,
    Tier,
    call,
    evaluation,
    model_id,
)
from abacus.ai_gateway.routes import configure_route, route_provider
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.modules.agents.api import (
    RESPONDER,
    AnalyzeFacts,
    NoticeAnalyzeOutput,
    NoticeExtractOutput,
    check_notice_answer,
    notice_context,
    spec,
)
from abacus_tools.evals.gate import COST_TOLERANCE
from abacus_tools.evals.notices_responder import (
    AnalyzeAnswer,
    AnalyzeCase,
    Attempt,
    ExtractAnswer,
    ExtractCase,
    Subset,
    Suite,
    load,
    run,
)
from abacus_tools.evals.runner import EvalRoute, baseline, guard, guard_real, prepare
from abacus_tools.evals.summary import SIGNING_KEY_ENV
from abacus_tools.evals.upload_review import ADMISSION_TRIES
from abacus_tools.evals.upload_review import (
    _Recording as Recording,  # pyright: ignore[reportPrivateUsage] -- the same recording provider
)
from abacus_tools.stack import Seeded, Stack, connect_db, run_with_stack

MODES: Final = ("analyze", "extract")
# The thresholds each mode clears on; consent is the gate's, and counts for both.
MODE_METRICS: Final = {
    "analyze": frozenset(
        {
            "amounts_by_code",
            "citation_verification",
            "position_accuracy",
            "recommendation_in_options",
            "adversarial_containment",
            "consent_refusal",
        }
    ),
    "extract": frozenset(
        {
            "extract.field_exact_match.clean",
            "extract.field_exact_match.degraded",
            "extract.low_confidence_flag_recall",
            "extract.confident_wrong_rate",
            "consent_refusal",
        }
    ),
}


@dataclass(frozen=True)
class Seen:
    """One attempt: its case, the answer (None: errored or refused by the gateway) and cost."""

    case_id: str
    mode: str
    attempt: int
    cost_usd: Decimal
    answer: dict[str, object] | None = None
    refused_by_code: str | None = None
    error: str | None = None
    raw: tuple[str, ...] = field(default_factory=tuple[str, ...])


async def _run_row(superuser: str, world: Seeded) -> uuid.UUID:
    """An agent run for the attempt's usage records, on the synthetic firm."""
    responder = spec(RESPONDER)
    run_id = uuid.uuid4()
    conn = await connect_db(superuser)
    try:
        await conn.execute(
            "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            run_id,
            world.tenant,
            responder.id,
            responder.version,
            world.engagement,
            world.user,
            sorted(responder.task_scope),
        )
    finally:
        await conn.close()
    return run_id


async def _cost(superuser: str, run_id: uuid.UUID) -> Decimal:
    conn = await connect_db(superuser)
    try:
        cost = await conn.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_records WHERE agent_run_id = $1", run_id
        )
    finally:
        await conn.close()
    return Decimal(str(cost))


def facts_of(case: AnalyzeCase) -> AnalyzeFacts:
    """Code's facts for a case, as the analysis hands them to the responder."""
    rows = tuple(
        {"key": r.key, "label": r.label, "filed": str(r.filed), "irs": str(r.irs),
         "difference": str(r.difference)}
        for r in case.rows
    )  # fmt: skip
    return AnalyzeFacts(
        rows, (), (), tuple(case.options), tuple((ln.ref, ln.text) for ln in case.document_lines)
    )


def _attribution(run_id: uuid.UUID, world: Seeded) -> Attribution:
    return Attribution(
        TenantContext(world.tenant, "system", "evals"), world.engagement, RESPONDER, run_id
    )


def analyze_call(
    case: AnalyzeCase, run_id: uuid.UUID, world: Seeded
) -> GatewayCall[NoticeAnalyzeOutput]:
    """The analysis's own call (`notice_responder.analyze`), on the case's facts."""
    responder = spec(RESPONDER)
    return GatewayCall(
        purpose=responder.purpose,
        prompt=responder.prompt,
        tier=responder.tier,
        output_schema=NoticeAnalyzeOutput,
        budget_usd=responder.limits.max_cost_usd,
        attribution=_attribution(run_id, world),
        context=notice_context(facts_of(case), ()),
        work_class=responder.work_class,
        essential=responder.essential,
        routes=responder.routes,
        cheaper_tiers=responder.cheaper_tiers,
        max_output_tokens=responder.limits.max_output_tokens,
        timeout_seconds=responder.limits.max_seconds,
    )


def extract_call(
    case: ExtractCase, run_id: uuid.UUID, world: Seeded
) -> GatewayCall[NoticeExtractOutput]:
    """The intake's own call (`notice_responder.extract_fields`), on the case's word layer."""
    responder = spec(RESPONDER)
    mode = responder.modes["extract"]
    keys = sorted({f.field_key for f in case.expected_fields})
    lines = [{"ref": ln.ref, "text": ln.text} for ln in case.document_lines]
    context = ContextBuilder().task({"keys": keys, "lines": lines}, untrusted=["lines"]).build()
    return GatewayCall(
        purpose=responder.purpose,
        prompt=mode.prompt,
        tier="small",
        output_schema=NoticeExtractOutput,
        budget_usd=mode.max_cost_usd,
        attribution=_attribution(run_id, world),
        context=context,
        work_class=responder.work_class,
        essential=responder.essential,
        routes=responder.routes,
        cheaper_tiers=responder.cheaper_tiers,
        max_output_tokens=responder.limits.max_output_tokens,
        timeout_seconds=60,
    )


async def admitted[T: BaseModel](request: GatewayCall[T], route: str) -> T | None:
    """The call's output, waiting out admission a few times; None when it never answered."""
    for _ in range(ADMISSION_TRIES):
        try:
            with evaluation(request.tier, route):  # pyright: ignore[reportArgumentType] -- a validated route name
                return (await call(request)).output
        except NotAdmitted as refused:
            await asyncio.sleep(min(max(float(refused.retry_after or 5), 2.0), 30.0))
    return None


async def attempt(
    case: AnalyzeCase | ExtractCase, n: int, world: Seeded, stack: Stack, route: str
) -> Seen:
    seen: list[ModelRequest] = []
    said: list[str] = []
    configure_route(route, Recording(route_provider(route), seen, said))  # pyright: ignore[reportArgumentType] -- a validated route name
    try:
        run_id = await _run_row(stack.superuser, world)
        refused: str | None = None
        if isinstance(case, AnalyzeCase):
            analyzed = await admitted(analyze_call(case, run_id, world), route)
            output: BaseModel | None = analyzed
            if analyzed is not None:
                refused = check_notice_answer(analyzed, facts_of(case))
        else:
            output = await admitted(extract_call(case, run_id, world), route)
        cost = await _cost(stack.superuser, run_id)
        if output is None:
            return Seen(case.id, case.mode, n, cost, error="no_output", raw=tuple(said))
        return Seen(
            case.id, case.mode, n, cost, output.model_dump(mode="json"), refused, raw=tuple(said)
        )
    except Exception as exc:
        return Seen(case.id, case.mode, n, Decimal(0), error=f"{type(exc).__name__}: {exc}"[:300])
    finally:
        configure_route(route, None)  # pyright: ignore[reportArgumentType] -- a validated route name


def graded(
    suite: Suite, chosen: Sequence[AnalyzeCase | ExtractCase], seen: Sequence[Seen]
) -> list[Attempt]:
    """Each answered attempt as its case and answer, for `run`."""
    by_id = {c.id: c for c in chosen}
    out: list[Attempt] = []
    for s in seen:
        case = by_id[s.case_id]
        if s.answer is None:
            continue
        if isinstance(case, AnalyzeCase):
            out.append((case, AnalyzeAnswer.model_validate(s.answer)))
        else:
            out.append((case, ExtractAnswer.model_validate(s.answer)))
    return out


def median_cost(seen: Sequence[Seen], mode: str) -> Decimal | None:
    costs = [s.cost_usd for s in seen if s.mode == mode and s.answer is not None]
    return Decimal(str(statistics.median(costs))) if costs else None


def clearance(
    suite: Suite,
    route: str,
    failed: Sequence[str],
    seen: Sequence[Seen],
    baselines: dict[str, Decimal | None],
) -> dict[str, dict[str, object]]:
    """Per mode: whether this run clears it, and every reason it doesn't (fail closed)."""
    out: dict[str, dict[str, object]] = {}
    for mode in MODES:
        reasons: list[str] = []
        if route != "bedrock":
            reasons.append("not_bedrock")
        reasons += sorted(m for m in failed if m in MODE_METRICS[mode])
        if not any(s.mode == mode for s in seen):
            reasons.append("no_attempts")
        if any(s.mode == mode and s.answer is None for s in seen):
            reasons.append("errored")
        cost, limit = median_cost(seen, mode), baselines.get(mode)
        if limit is None:
            reasons.append("cost_regression:no_baseline")
        elif cost is not None and cost > limit * (1 + COST_TOLERANCE):
            reasons.append("cost_regression")
        if mode == "analyze" and suite.label_review != "reviewed":
            reasons.append("label_review_pending")
        out[mode] = {"cleared": not reasons, "reasons": reasons, "median_cost_usd": str(cost)}
    return out


def signed(report: dict[str, object]) -> dict[str, object]:
    """The report with CI's HMAC-SHA256 over its canonical JSON, when the key is configured."""
    key = os.environ.get(SIGNING_KEY_ENV)
    if not key:
        return report
    body = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str).encode()
    return {**report, "signature": hmac.new(key.encode(), body, hashlib.sha256).hexdigest()}


def verified(report: dict[str, object]) -> bool:
    key, signature = os.environ.get(SIGNING_KEY_ENV), report.get("signature")
    if not key or not isinstance(signature, str):
        return False
    body = {k: v for k, v in report.items() if k != "signature"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    expected = hmac.new(key.encode(), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def evaluate(
    stack: Stack, world: Seeded, suite: Suite, route: str, out: Path, subset: Subset
) -> dict[str, object]:
    chosen = [c for c in suite.cases if subset == "full" or c.fast]
    unreadable = [c.id for c in chosen if isinstance(c, ExtractCase) and not c.document_lines]
    started = system_now()
    seen: list[Seen] = []
    total, aborted = Decimal(0), False
    for case in chosen:
        if case.id in unreadable:
            continue
        for n in range(1, suite.repeats + 1):
            if total >= suite.cost_limit_usd:
                aborted = True
                break
            result = await attempt(case, n, world, stack, route)
            total += result.cost_usd
            seen.append(result)
    summary = run(suite, subset=subset, route=route, attempts=graded(suite, chosen, seen))
    tiers: dict[str, Tier] = {"analyze": spec(RESPONDER).tier, "extract": "small"}
    baselines = {mode: baseline(RESPONDER, tiers[mode]) for mode in MODES}
    cleared = clearance(suite, route, summary.failed_thresholds, seen, baselines)
    status = summary.status
    if aborted or unreadable:
        status = "failed"
    report: dict[str, object] = {
        "agent": RESPONDER,
        "suite_version": suite.version,
        "prompts": {
            "analyze": spec(RESPONDER).prompt,
            "extract": spec(RESPONDER).modes["extract"].prompt,
        },
        "models": {m: model_id(t, route) for m, t in tiers.items()},  # pyright: ignore[reportArgumentType] -- a validated route name
        "route": route,
        "subset": subset,
        "label_review": suite.label_review,
        "status": status,
        "aborted_cost": aborted,
        "extract_cases_without_lines": unreadable,
        "metrics": summary.metrics,
        "failed_thresholds": summary.failed_thresholds,
        "clearance": cleared,
        "total_cost_usd": str(total),
        "started_at": started.isoformat(),
        "finished_at": system_now().isoformat(),
        "attempts": [
            {k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(s).items()}
            for s in seen
        ],
    }
    report = signed(report)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"notices_responder-{route}-{uuid.uuid4()}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"{RESPONDER} {route}: {status} {summary.metrics} cost ${total} -> {path}")
    print(json.dumps(cleared, indent=2))
    return report


def real_main(route: str, out: Path, subset: Subset = "full") -> int:
    """N-04-T25's real run, in the evaluation environment with an enabled route."""
    guard()
    guard_real(cast(EvalRoute, route))
    suite = load()
    results: list[dict[str, object]] = []

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        results.append(await evaluate(stack, world, suite, route, out, subset))

    run_with_stack(record)
    return 0 if results and results[0]["status"] == "passed" else 1
