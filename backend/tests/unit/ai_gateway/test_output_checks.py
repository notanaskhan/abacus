"""P-09-T04 (TASK-5005): the additive output-check registry; call() never consults it."""

from __future__ import annotations

import inspect
from uuid import UUID

import pytest

import abacus.ai_gateway as gateway
from abacus.ai_gateway.output_checks import (
    CheckFailure,
    register_output_check,
    registered_kinds,
    run_output_check,
    settle,
)
from abacus.modules.agents.blocks import BlocksTurn, Fact

FACTS = {"total": Fact(id="total", kind="money", value="100.00", basis="tb:final")}


def _turn(text: str) -> BlocksTurn:
    return BlocksTurn(
        {"parts": [{"kind": "p", "segments": [{"kind": "text", "text": text}]}]}, FACTS, set()
    )


def test_ac1_the_agents_module_registers_agent_blocks() -> None:
    assert "agent_blocks" in registered_kinds()
    assert run_output_check("agent_blocks", _turn("The trial balance ties")) is None


def test_ac2_a_free_number_is_repaired_once_then_unsupported() -> None:
    first = settle("agent_blocks", _turn("The total is 100"), repairs_used=0)
    assert first.outcome == "repair"
    assert first.failure == CheckFailure("free_number", "parts[0].segments[0]")
    second = settle("agent_blocks", _turn("The total is 100"), repairs_used=first.repairs_used)
    assert second.outcome == "unsupported"
    fixed = settle("agent_blocks", _turn("The total ties to the ledger"), repairs_used=1)
    assert fixed.outcome == "passed"


def test_ac2_an_unknown_kind_fails_closed_without_a_repair() -> None:
    assert settle("no_such_kind", {}, repairs_used=0).outcome == "unsupported"


def test_ac2_a_failure_never_carries_the_text() -> None:
    failure = run_output_check("agent_blocks", _turn("I approved it"))
    assert failure is not None and "approved" not in failure.code + failure.where


def test_ac3_one_check_per_kind() -> None:
    def other(_: object) -> CheckFailure | None:
        return None

    with pytest.raises(ValueError, match="already has a check"):
        register_output_check("agent_blocks", other)


def test_ac4_call_never_consults_the_registry() -> None:
    source = inspect.getsource(gateway.call) + inspect.getsource(gateway._call)  # pyright: ignore[reportPrivateUsage] -- the guard reads the private turn
    assert "output_check" not in source and "settle(" not in source


def test_ac4_citations_must_be_the_runs() -> None:
    turn = BlocksTurn(
        {
            "parts": [
                {
                    "kind": "cite_list",
                    "cites": [{"kind": "cite", "citation_id": str(UUID(int=5)), "n": 1}],
                }
            ]
        },
        FACTS,
        set(),
    )
    assert run_output_check("agent_blocks", turn) == CheckFailure(
        "unknown_citation", "parts[0].cites[0]"
    )
