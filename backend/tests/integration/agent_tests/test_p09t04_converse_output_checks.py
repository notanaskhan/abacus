"""P-09-T04 (TASK-6204; SPEC-648 AC-7; DEC-2804): `converse()` runs the output-check registry on
structured final turns: one repair, then Unsupported. `call()` and the live screener, matcher and
upload-reviewer paths never consult it.

Row acceptance: "Additive gateway output-check registry ai_gateway/output_checks.py that converse
runs on structured final turns (one repair, then Unsupported or escalated); call and the live
screener, matcher and upload-reviewer paths untouched."
"""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Iterator
from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import BaseModel

import abacus.ai_gateway as gateway
from abacus.ai_gateway import Attribution, CheckFailure, FakeModel, configure_provider
from abacus.ai_gateway import output_checks as oc
from abacus.ai_gateway import providers as p
from abacus.ai_gateway.converse import ConverseCall, converse
from abacus.kernel.db import TenantContext

from .support import Seeder, World

pytestmark = pytest.mark.asyncio
REF = "evidence.screen@v0"
KIND = "p09t04_test_kind"


class Turn(BaseModel):
    text: str


def _check(output: object) -> CheckFailure | None:
    assert isinstance(output, Turn)
    return None if "ok" in output.text else CheckFailure("free_number", "blocks.0.text")


@pytest.fixture(autouse=True)
def _kind(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(oc._CHECKS, KIND, _check)  # pyright: ignore[reportPrivateUsage]
    yield
    configure_provider(None)


@pytest.fixture(autouse=True)
async def _unblocked(seed: Seeder) -> None:
    await seed.run("DELETE FROM provider_capacity")


def _call(world: World, kind: str = KIND) -> ConverseCall[Turn]:
    run = uuid.uuid4()
    return ConverseCall(
        purpose="P-09-T04 output check",
        prompt=REF,
        tier="small",
        budget_usd=Decimal("1.00"),
        attribution=Attribution(
            TenantContext(
                world.tenant_id, "agent", f"agent:evidence.screener:{run}", uuid.uuid4()
            ),
            world.engagement_id,
            "evidence.screener",
            run,
        ),
        work_class="interactive",
        essential=False,
        routes=("direct",),
        messages=(p.ConverseMessage("user", (p.TextBlock("Summarise."),)),),
        output_schema=Turn,
        output_kind=kind,
    )


def _script(*texts: str) -> None:
    fake = FakeModel()
    fake.script(REF, [p.FinalTurn(t) for t in texts])
    configure_provider(fake)


async def test_a_turn_that_passes_its_check_is_shown(world: World) -> None:
    _script('{"text": "ok: 3 open"}')
    result = await converse(_call(world))
    assert result.status == "ok"
    assert result.output == Turn(text="ok: 3 open")


async def test_one_repair_then_the_turn_passes(world: World) -> None:
    _script('{"text": "about 40"}', '{"text": "ok"}')
    result = await converse(_call(world))
    assert result.status == "repaired"
    assert result.attempts == 2


async def test_a_turn_failing_twice_settles_unsupported_and_is_never_shown(world: World) -> None:
    _script('{"text": "about 40"}', '{"text": "still about 40"}')
    result = await converse(_call(world))
    assert result.status == "unsupported"
    assert result.output is None
    assert result.failure == "output_check"
    assert result.failure_where == "free_number@blocks.0.text"


async def test_an_unregistered_kind_fails_closed_without_a_repair(world: World) -> None:
    _script('{"text": "ok"}', '{"text": "ok"}')
    result = await converse(_call(world, kind="no_such_kind"))
    assert result.status == "unsupported"
    assert result.attempts == 1
    assert result.failure_where == "no_check@no_such_kind"


async def test_without_a_kind_the_registry_is_not_consulted(world: World) -> None:
    _script('{"text": "about 40"}')
    result = await converse(replace(_call(world), output_kind=None))
    assert result.status == "ok"


def test_call_and_the_live_specialists_never_consult_the_registry() -> None:
    source = inspect.getsource(gateway._call)  # pyright: ignore[reportPrivateUsage]
    assert "settle" not in source
    assert "run_output_check" not in source
    assert "agent_blocks" in oc.registered_kinds()
