"""Capability runs of `assurance.post_issuance_analysis` v1 against Q-05-T10's frozen suite
(Q-05-T22; TASK-8909; ADR-079).

    python -m abacus_tools.evals --agent post_issuance_analysis --route fake|direct|bedrock

Each graded case goes through the capability's own path: code builds its input (the case's facts,
code's options and the option code marks eligible, both certifications as untrusted pages: the
case's source text as the corrected certification and the certified trust report's heading), the
model answers (`fake`: the case's recorded answer in the capability's shape; `direct` / `bedrock`:
one gateway call with `audit.post_issuance_analysis@v1` on a throwaway stack's synthetic firm), and
**code settles** it (`post_issuance_analysis.settle`: number provenance, the eligible-only tag,
quotes from both certifications, the closing sentences). The settled analysis is graded by
`post_issuance_analysis.run`, the suite's own graders. An analysis that leaves the tag empty is
graded with the option code derives for the case (Notify users when a disclosure is affected,
otherwise Revise and reissue): the capability never recommends an option code does not mark
eligible (DEC-5911).

The report is signed (HMAC-SHA256, `ABACUS_EVAL_SIGNING_KEY`). Only a Bedrock report that passes
every frozen threshold clears the capability; a person records it in
`evals/post_issuance_analysis/clearance.yaml` and its cost in `evals/baselines.yaml` (both
protected) from the signed report (DEC-5901).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final, Literal, cast

from abacus.modules.assurance import post_issuance_analysis as pia
from abacus_tools.evals.post_issuance_analysis import (
    SUITE,
    Case,
    Output,
    Suite,
    eligible_no_action,
    load,
    run,
)
from abacus_tools.evals.summary import SIGNING_KEY_ENV

ROUTES: Final = ("fake", "direct", "bedrock")
CERTIFIED_TEXT: Final = "Certified trust report. Statement of Net Assets Available for Benefits."
CERTIFIED_QUOTE: Final = "Statement of Net Assets Available for Benefits"
_TOKEN: Final = re.compile(r"\{\{fact:([a-z_]+)\}\}")
REFUSED: Final = Output(prose="", recommendation="revise_and_reissue", citations=[], actions=[])


def _kind(key: str) -> str:
    return "percent" if "pct" in key else "money"


def given(case: Case) -> pia.PostIssuanceAnalysisInput:
    eligible = "no_action" if eligible_no_action(case) else None
    return pia.PostIssuanceAnalysisInput(
        case_ref="PI-01" if case.category == "golden" else case.id[:10],
        facts=[
            pia.FactIn(id=k, kind=cast(Literal["money", "percent", "count"], _kind(k)), value=v)
            for k, v in sorted(case.facts.items())
        ],
        options=["no_action", "revise_and_reissue", "notify_users"],
        eligible=cast(pia.Option | None, eligible),
        disclosure_affected=case.disclosure_affected,
        sources=[
            pia.SourceIn(source="certified", evidence_version_id=uuid.UUID(int=1), pages=[1]),
            pia.SourceIn(source="corrected", evidence_version_id=uuid.UUID(int=2), pages=[1]),
        ],
        untrusted=[f"certified certification page 1: {CERTIFIED_TEXT}",
                   f"corrected certification page 1: {case.source_text}"],
    )  # fmt: skip


def _blocks(prose: str) -> dict[str, object]:
    """The recorded prose as AgentBlocks: `{{fact:x}}` tokens become fact segments; the suite's
    not-decided sentence is code's to add, so it is dropped here."""
    body = prose.replace(pia.SUITE_NOT_DECIDED, "").strip()
    segments: list[dict[str, object]] = []
    at = 0
    for m in _TOKEN.finditer(body):
        if m.start() > at:
            segments.append({"kind": "text", "text": body[at : m.start()]})
        segments.append({"kind": "fact", "fact_id": m.group(1)})
        at = m.end()
    if at < len(body):
        segments.append({"kind": "text", "text": body[at:]})
    return {"version": 1, "parts": [{"kind": "p", "segments": segments or [
        {"kind": "text", "text": "The case was compared by code."}]}]}  # fmt: skip


def recorded_answer(case: Case) -> pia.PostIssuanceAnalysisOutput:
    """The fake model's answer: the recorded analysis in the capability's shape (its tag only
    when the recorded recommendation is the option code marks eligible)."""
    o = case.output
    tag = o.recommendation if o.recommendation == "no_action" else None
    return pia.PostIssuanceAnalysisOutput(
        blocks=_blocks(o.prose),
        recommendation=tag,
        quotes=[
            pia.QuoteOut(source="certified", page=1, quote=CERTIFIED_QUOTE),
            *[pia.QuoteOut(source="corrected", page=1, quote=q[:200]) for q in o.citations][:9],
        ],
    )


def _prose(blocks: Mapping[str, object]) -> str:
    out: list[str] = []
    for part in cast("list[dict[str, object]]", blocks.get("parts") or []):
        for seg in cast("list[dict[str, object]]", part.get("segments") or []):
            if seg.get("kind") == "fact":
                out.append("{{fact:" + str(seg.get("fact_id")) + "}}")
            else:
                out.append(str(seg.get("text", "")))
        out.append(" ")
    return "".join(out).strip()


def to_output(case: Case, settled: pia.Settled) -> Output:
    derived = "notify_users" if case.disclosure_affected else "revise_and_reissue"
    return Output(
        prose=_prose(settled.blocks),
        recommendation=settled.recommendation or derived,
        citations=[q.quote for q in settled.quotes if q.source == "corrected"],
        actions=[],
    )


def screen(
    case: Case,
    answer: Callable[[pia.PostIssuanceAnalysisInput], pia.PostIssuanceAnalysisOutput],
) -> tuple[Output, str | None]:
    request = given(case)
    try:
        settled = pia.settle(request, answer(request))
    except pia.OutputRefused as refused:
        return REFUSED, str((refused.facts or {}).get("reason"))
    except ValueError:
        return REFUSED, "schema"
    return to_output(case, settled), None


def signed(report: dict[str, object]) -> dict[str, object]:
    key = os.environ.get(SIGNING_KEY_ENV)
    if not key:
        return report
    body = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str).encode()
    return {**report, "signature": hmac.new(key.encode(), body, hashlib.sha256).hexdigest()}


def report_for(
    suite: Suite, route: str, outputs: Mapping[str, Output], refusals: Mapping[str, str]
) -> dict[str, object]:
    result = run(suite, outputs=outputs)
    golden = next((c for c in suite.cases if c.category == "golden"), None)
    ends = (
        outputs[golden.id].prose.rstrip().endswith(pia.FINAL)
        if golden is not None and golden.id in outputs
        else False
    )
    return signed(
        {
            "suite": SUITE, "suite_version": suite.version, "capability": pia.CAPABILITY,
            "prompt": pia.PROMPT, "route": route, "passed": result.passed,
            "seeded_caught": result.seeded_caught, "rates": result.rates,
            "golden_ends_not_decided": ends, "refused_by_code": dict(sorted(refusals.items())),
            "clears_real_firms": route == "bedrock" and result.passed and ends,
        }
    )  # fmt: skip


def fake_main(out: Path) -> int:
    suite = load()
    outputs: dict[str, Output] = {}
    refusals: dict[str, str] = {}
    for case in suite.cases:
        if case.category == "seeded":
            continue
        found, reason = screen(case, lambda _req, c=case: recorded_answer(c))
        outputs[case.id] = found
        if reason is not None:
            refusals[case.id] = reason
    report = report_for(suite, "fake", outputs, refusals)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{SUITE}-fake.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["passed"] and report["golden_ends_not_decided"] else 1


def real_main(route: str, out: Path) -> int:
    """The evaluation account's direct or Bedrock run (a person's step, DEC-5901)."""
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call, evaluation
    from abacus.kernel.db import TenantContext
    from abacus.modules.agents.api import spec_v2
    from abacus_tools.evals.runner import EvalRoute, guard, guard_real, prepare
    from abacus_tools.stack import Stack, run_with_stack

    guard()
    guard_real(cast(EvalRoute, route))
    suite = load()
    spec = spec_v2(pia.CAPABILITY)
    reports: list[dict[str, object]] = []

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        outputs: dict[str, Output] = {}
        refusals: dict[str, str] = {}
        for case in suite.cases:
            if case.category == "seeded":
                continue
            request = given(case)
            attribution = Attribution(
                TenantContext(world.tenant, "system", "evals"), world.engagement,
                pia.CAPABILITY, uuid.uuid4(),
            )  # fmt: skip
            try:
                with evaluation(spec.tier, route):  # pyright: ignore[reportArgumentType] -- validated
                    result = await call(
                        GatewayCall(
                            purpose=spec.purpose, prompt=pia.PROMPT, tier=spec.tier,
                            output_schema=pia.PostIssuanceAnalysisOutput,
                            budget_usd=spec.limits.max_cost_usd, attribution=attribution,
                            context=ContextBuilder()
                            .task(request.model_dump(mode="json"), untrusted=("untrusted",))
                            .build(),
                            work_class=spec.work_class, essential=spec.essential,
                            routes=spec.routes, cheaper_tiers=spec.cheaper_tiers,
                            max_output_tokens=spec.limits.max_output_tokens,
                            timeout_seconds=spec.limits.max_seconds,
                        )
                    )  # fmt: skip
                answer = cast(pia.PostIssuanceAnalysisOutput, result.output)
                found, reason = screen(case, lambda _req, a=answer: a)
            except Exception as exc:  # an errored attempt is graded as refused
                found, reason = REFUSED, type(exc).__name__
            outputs[case.id] = found
            if reason is not None:
                refusals[case.id] = reason
        reports.append(report_for(suite, route, outputs, refusals))

    run_with_stack(record)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{SUITE}-{route}-{uuid.uuid4()}.json"
    path.write_text(json.dumps(reports[0] if reports else {}, indent=2), encoding="utf-8")
    return 0 if reports and reports[0]["passed"] else 1


def main(route: str, out: Path) -> int:
    if route not in ROUTES:
        raise ValueError(route)
    return fake_main(out) if route == "fake" else real_main(route, out)


__all__ = ["fake_main", "given", "main", "real_main", "recorded_answer", "screen", "to_output"]
