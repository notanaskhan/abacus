"""Q-02 AC-22 (Q-02-T32; ADR-167 §2): the gateway refuses a context holding an unmasked TIN.

Before any network call, the gateway scans the system prompt and every context part (the text
layers, the task JSON and its untrusted blocks) for SSN, ITIN and EIN forms that pass their
validity rules. A match is refused with boundary reason `pii_in_context`, audited as
`ai.boundary_refused` with the reason and the part's name and never the value, and never retried
or rerouted, on every route, the fake one included. Masked forms pass.

Valid numbers are generated at run time from the rules; the fixed one is a 9xx ITIN form
(ADR-085). The unit of work is replaced by a recorder, so no database is needed: the refusal
happens before the gateway reads anything.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    ContextBuilder,
    DataBoundaryRefused,
    FakeModel,
    GatewayCall,
    ModelRequest,
    boundary,
    call,
    configure_provider,
)
from abacus.ai_gateway.pii import PARTS, ContextPart, part_with_tin
from abacus.kernel.classification import mask
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Ref

PROMPT = "evidence.screen@v0"
AGENT = "test.pii_backstop"  # no prompt-variant flag: the call reads nothing before the scan
ITIN = "900-70-1234"  # 9xx area, ITIN middle pair: passes the ITIN rules, never an SSN
_INVALID_EIN_PREFIXES = {0, 7, 8, 9, 17, 18, 19, 28, 29, 49, 69, 70, 78, 79, 89, 96, 97}
_ITIN_GROUPS = [*range(50, 66), *range(70, 89), *range(90, 93), *range(94, 100)]


class Verdict(BaseModel):
    ok: bool


@dataclass
class _Audit:
    records: list[tuple[str, dict[str, str | int]]] = field(
        default_factory=list[tuple[str, dict[str, str | int]]]
    )

    def record(self, action: str, *, after: Ref | None = None, **_: object) -> None:
        self.records.append((action, dict(after.fields) if after else {}))


@pytest.fixture
def audit(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Audit]:
    found = _Audit()

    @asynccontextmanager
    async def fake_uow(tenant: object) -> AsyncGenerator[_Audit]:
        yield found

    monkeypatch.setattr(boundary, "uow", fake_uow)
    yield found


@pytest.fixture
def reached() -> Iterator[list[ModelRequest]]:
    seen: list[ModelRequest] = []

    def responder(request: ModelRequest) -> str:
        seen.append(request)
        return '{"ok": true}'

    configure_provider(FakeModel({PROMPT: responder}))
    yield seen
    configure_provider(None)


def _call(context: AssembledContext) -> GatewayCall[Verdict]:
    return GatewayCall(
        purpose="screen a document",
        prompt=PROMPT,
        tier="small",
        output_schema=Verdict,
        work_class="time_sensitive",
        essential=True,
        routes=("bedrock", "direct"),
        budget_usd=Decimal("0.05"),
        attribution=Attribution(
            TenantContext(uuid.uuid4(), "agent", f"agent:{AGENT}:{uuid.uuid4()}"),
            uuid.uuid4(),
            AGENT,
            uuid.uuid4(),
        ),
        context=context,
    )


def _in_part(part: ContextPart, value: str) -> AssembledContext:
    builder = ContextBuilder()
    if part in ("firm", "engagement", "examples"):
        builder.text(part, f"Notes: {value} on file.")
        return builder.task({"balanced": True}).build()
    if part == "untrusted":
        return builder.task(
            {"balanced": True, "document": {"lines": ["W-2", f"box a {value}"]}},
            untrusted=("document",),
        ).build()
    return builder.task({"balanced": True, "rows": [{"payee_tin": value}]}).build()


# --- refused, audited, never sent ----------------------------------------------------------------

CONTEXT_PARTS: tuple[ContextPart, ...] = ("firm", "engagement", "examples", "task", "untrusted")


@pytest.mark.parametrize("part", CONTEXT_PARTS)
async def test_ac22_an_unmasked_tin_in_any_part_is_refused_before_any_network_call(
    audit: _Audit, reached: list[ModelRequest], part: ContextPart
) -> None:
    with pytest.raises(DataBoundaryRefused) as raised:
        await call(_call(_in_part(part, ITIN)))
    assert raised.value.reason == "pii_in_context"
    assert reached == []  # the provider never ran: not called, not retried, not rerouted
    assert audit.records == [
        (
            "ai.boundary_refused",
            {
                "reason": boundary.REASONS.index("pii_in_context"),
                "part": PARTS.index(part),
            },
        )
    ]
    assert ITIN not in str(raised.value)


async def test_ac22_the_refusal_names_no_value_in_its_log_line(
    audit: _Audit, reached: list[ModelRequest], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(DataBoundaryRefused):
        await call(_call(_in_part("untrusted", ITIN)))
    out = capsys.readouterr()
    logged = out.out + out.err
    assert "ai.boundary_refused" in logged and "pii_in_context" in logged
    assert ITIN not in logged and "900701234" not in logged


async def test_ac22_a_second_identical_call_is_refused_again_and_never_sent(
    audit: _Audit, reached: list[ModelRequest]
) -> None:
    for _ in range(2):
        with pytest.raises(DataBoundaryRefused):
            await call(_call(_in_part("task", ITIN)))
    assert reached == []
    assert [action for action, _ in audit.records] == ["ai.boundary_refused"] * 2


def test_ac22_the_reason_is_appended_so_earlier_indices_keep_their_meaning() -> None:
    assert boundary.REASONS[:6] == ("route", "terms", "firm", "agent", "engagement", "stage")
    assert boundary.REASONS[6] == "pii_in_context"


def test_ac22_the_parts_are_the_prompt_the_layers_and_the_untrusted_blocks() -> None:
    assert PARTS == ("instructions", "firm", "engagement", "examples", "task", "untrusted")


def test_ac22_a_tin_in_the_system_prompt_is_found_too() -> None:
    clean = ContextBuilder().task({"balanced": True}).build()
    assert part_with_tin(f"Use {ITIN}.", clean) == "instructions"
    assert part_with_tin("Screen the document.", clean) is None


# --- masked forms pass --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "masked", [mask(ITIN, "tin"), "XX-XXX1234", "***-**-1234", "last four 1234", "90070123"]
)
@pytest.mark.parametrize("part", CONTEXT_PARTS)
def test_ac22_masked_forms_pass_the_scan(masked: str, part: ContextPart) -> None:
    assert part_with_tin("Screen the document.", _in_part(part, masked)) is None


def test_ac22_numbers_that_fail_the_rules_pass_the_scan() -> None:
    for value in ("900-45-6789", "000-12-3456", "07-1234567", "123456789.50"):
        assert part_with_tin("", _in_part("task", value)) is None, value


# --- property: any valid TIN, any part, any form -------------------------------------------------


def _ssn(area: int, group: int, serial: int) -> str:
    return f"{area:03d}{group:02d}{serial:04d}"


def _itin(area: int, group: int, serial: int) -> str:
    return f"9{area:02d}{group:02d}{serial:04d}"


def _ein(prefix: int, serial: int) -> str:
    return f"{prefix:02d}{serial:07d}"


ssns = st.builds(
    _ssn,
    st.integers(1, 899).filter(lambda a: a != 666),
    st.integers(1, 99),
    st.integers(1, 9999),
)
itins = st.builds(
    _itin,
    st.integers(0, 99),
    st.sampled_from(_ITIN_GROUPS),
    st.integers(0, 9999),
)
eins = st.builds(
    _ein,
    st.integers(0, 99).filter(lambda p: p not in _INVALID_EIN_PREFIXES),
    st.integers(0, 9_999_999),
)
forms = st.one_of(
    st.tuples(st.one_of(ssns, itins), st.sampled_from(["", "-", " "])).map(
        lambda t: f"{t[0][:3]}{t[1]}{t[0][3:5]}{t[1]}{t[0][5:]}"
    ),
    eins.map(lambda d: f"{d[:2]}-{d[2:]}"),
    eins,
)


@given(value=forms, part=st.sampled_from(CONTEXT_PARTS))
@settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_ac22_property_any_valid_tin_in_any_part_is_found_and_its_mask_passes(
    value: str, part: ContextPart
) -> None:
    assert part_with_tin("Screen the document.", _in_part(part, value)) == part
    assert part_with_tin("Screen the document.", _in_part(part, mask(value, "tin"))) is None


@given(value=forms, part=st.sampled_from(CONTEXT_PARTS))
@settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_ac22_property_the_gateway_refuses_every_one_and_never_calls_the_provider(
    audit: _Audit, reached: list[ModelRequest], value: str, part: ContextPart
) -> None:
    async def attempt() -> str:
        try:
            await call(_call(_in_part(part, value)))
        except DataBoundaryRefused as refused:
            return refused.reason
        return "sent"

    assert asyncio.run(attempt()) == "pii_in_context"
    assert reached == []
