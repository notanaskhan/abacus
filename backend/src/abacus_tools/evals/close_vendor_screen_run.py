"""Capability runs of `close.agent` mode `vendor_screen` against C-02-T51's frozen suite (C-02-T34;
TASK-8906; ADR-079).

    python -m abacus_tools.evals --agent close_vendor_screen --route fake|direct|bedrock

Each graded case goes through the capability's own path: code builds the mode's input (the
offered entity types, the W-9's one page, its text scrubbed of any four-digit run and passed as
untrusted), the model answers (`fake`: the case's recorded answer, as the fake model gives it;
`direct` / `bedrock`: one gateway call with `close.agent.vendor_screen@v1` on a throwaway stack's
synthetic firm), and **code settles** it (`agent.settle`, so a TIN fragment, an option not offered
or a page not offered is refused and shows nothing). The settled screen is mapped to the suite's
output and graded by `close_vendor_screen.run`, the same graders as T51's recorded run.

The report is signed with CI's key (HMAC-SHA256, `ABACUS_EVAL_SIGNING_KEY`) and names its route;
only a Bedrock report whose every frozen threshold passes clears the capability for real firms,
recorded by a person from the signed report (DEC-5908). Real runs refuse outside the evaluation
environment (`guard_real`).
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
from typing import Final, cast

from abacus.modules.closes.api import VENDOR_ENTITY_TYPES as ENTITY_TYPES
from abacus.modules.closes.api import close_agent, scrub_digits
from abacus_tools.evals.close_vendor_screen import (
    SUITE,
    Case,
    Classification,
    Output,
    Suite,
    load,
    run,
)
from abacus_tools.evals.summary import SIGNING_KEY_ENV

ROUTES: Final = ("fake", "direct", "bedrock")
# AgentBlocks carry no free figure (number provenance): the recorded prose loses its digits.
_FIGURE_FREE: Final = re.compile(r"\s*\d[\d,.-]*")
# The suite's classes from the capability's entity types (T51 labels LLCs by their tax treatment
# and trusts with partnerships, as the W-9's line 3a reads).
TO_SUITE: Final[Mapping[str, Classification]] = {
    "individual": "individual",
    "single_member_llc": "llc_disregarded",
    "partnership": "partnership",
    "llc_p": "partnership",
    "trust_estate": "partnership",
    "c_corporation": "c_corporation",
    "llc_c": "c_corporation",
    "s_corporation": "s_corporation",
    "llc_s": "s_corporation",
    "other": "exempt_other",
}
FROM_SUITE: Final[Mapping[str, str]] = {
    "individual": "individual",
    "llc_disregarded": "single_member_llc",
    "partnership": "partnership",
    "c_corporation": "c_corporation",
    "s_corporation": "s_corporation",
    "exempt_other": "other",
}
CORPORATE: Final = frozenset({"c_corporation", "s_corporation"})
REFUSED: Final = Output(
    classification="exempt_other", exempt=False, reportable=True, prose="", citations=[]
)


def given(case: Case) -> close_agent.CloseAgentInput:
    """The mode's input for the case, as `vendor_screen.screen_vendor` builds it."""
    return close_agent.CloseAgentInput(
        mode="vendor_screen",
        close_id=uuid.UUID(int=0),
        facts=[],
        options=list(ENTITY_TYPES),
        pages=[1],
        untrusted=[
            f"Vendor name in the ledger: {case.vendor}"[:400],
            f"W-9 page 1: {scrub_digits(case.w9_text)}",
        ],
    )


def recorded_answer(case: Case) -> close_agent.CloseAgentOutput:
    """The fake model's answer for the case: its recorded screen, in the mode's output shape."""
    o = case.output
    sentence = _FIGURE_FREE.sub("", o.prose) or "Screened from the W-9."
    return close_agent.CloseAgentOutput(
        blocks={"version": 1, "parts": [{"kind": "p", "segments": [
            {"kind": "text", "text": sentence}]}]},
        screen=close_agent.VendorScreenOut(
            entity_type=FROM_SUITE[o.classification],
            is_attorney=case.is_attorney if o.reportable else False,
            exempt_reason="exempt_payee_code" if o.exempt else None,
            quotes=[close_agent.W9QuoteOut(page=1, quote=q[:200])
                    for q in (o.citations or ["Form W-9"])][:6],
        ),
    )  # fmt: skip


def to_output(case: Case, settled: close_agent.Settled) -> Output:
    """The settled screen as the suite's output. Reportable unless exempt (a corporation that is
    not an attorney, or a W-9 exemption code); the form is code's, not the model's."""
    screen = settled.screen
    if screen is None:
        return REFUSED
    cls = TO_SUITE.get(screen.entity_type, "exempt_other")
    exempt = screen.exempt_reason is not None or (cls in CORPORATE and not screen.is_attorney)
    prose = " ".join(
        str(seg.get("text", ""))
        for part in cast("list[dict[str, object]]", _dump(settled.blocks).get("parts") or [])
        for seg in cast("list[dict[str, object]]", part.get("segments") or [])
    )
    return Output(
        classification=cls,
        exempt=exempt,
        reportable=not exempt,
        form="1099-NEC" if not exempt else None,
        prose=prose[:500] or f"{case.vendor} is screened as {cls}.",
        citations=[q.quote for q in screen.quotes],
    )


def _dump(blocks: object) -> dict[str, object]:
    dump = getattr(blocks, "model_dump", None)
    return cast("dict[str, object]", dump(mode="json") if callable(dump) else blocks)


def screen(
    case: Case, answer: Callable[[close_agent.CloseAgentInput], close_agent.CloseAgentOutput]
) -> tuple[Output, str | None]:
    """One case through the capability's path; a refused answer shows nothing (REFUSED) and
    names its reason."""
    request = given(case)
    try:
        settled = close_agent.settle(request, answer(request))
    except close_agent.OutputRefused as refused:
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
    return signed(
        {
            "suite": SUITE,
            "suite_version": suite.version,
            "capability": close_agent.CAPABILITY,
            "prompt": close_agent.PROMPTS["vendor_screen"],
            "route": route,
            "passed": result.passed,
            "seeded_caught": result.seeded_caught,
            "rates": result.rates,
            "refused_by_code": dict(sorted(refusals.items())),
            "clears_real_firms": route == "bedrock" and result.passed,
        }
    )


def fake_main(out: Path) -> int:
    """C-02-T34's fake-model run: every case through settle, graded, signed (CI and the PR)."""
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
    return 0 if report["passed"] else 1


def real_main(route: str, out: Path) -> int:
    """The evaluation account's direct or Bedrock run (a person's step, DEC-5901): one gateway
    call per case on a throwaway stack's synthetic firm, settled and graded as the fake run."""
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call, evaluation
    from abacus.kernel.db import TenantContext
    from abacus.modules.agents.api import spec_v2
    from abacus_tools.evals.runner import EvalRoute, guard, guard_real, prepare
    from abacus_tools.stack import Stack, run_with_stack

    guard()
    guard_real(cast(EvalRoute, route))
    suite = load()
    spec = spec_v2(close_agent.CAPABILITY)
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
                close_agent.CAPABILITY, uuid.uuid4(),
            )  # fmt: skip
            try:
                with evaluation(spec.tier, route):  # pyright: ignore[reportArgumentType] -- validated
                    result = await call(
                        GatewayCall(
                            purpose=spec.purpose,
                            prompt=close_agent.PROMPTS["vendor_screen"],
                            tier=spec.tier,
                            output_schema=close_agent.CloseAgentOutput,
                            budget_usd=spec.limits.max_cost_usd,
                            attribution=attribution,
                            context=ContextBuilder()
                            .task(request.model_dump(mode="json"), untrusted=("untrusted",))
                            .build(),
                            work_class=spec.work_class,
                            essential=spec.essential,
                            routes=spec.routes,
                            cheaper_tiers=spec.cheaper_tiers,
                            max_output_tokens=spec.limits.max_output_tokens,
                            timeout_seconds=spec.limits.max_seconds,
                        )
                    )
                answer = cast(close_agent.CloseAgentOutput, result.output)
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
