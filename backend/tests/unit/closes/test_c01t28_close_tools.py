"""C-01-T28: the close tools on C17 (registry check, kinds, actions, the AJE draft by code)."""

from __future__ import annotations

from decimal import Decimal as D
from pathlib import Path

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.closes import agent_tools as tools

PROMPTS = Path(__file__).parents[3] / "src/abacus/ai_gateway/prompts"
NAMES = {
    "close.read_checklist": ("read", "close.read"),
    "close.reconcile": ("compute", "close.read"),
    "close.read_upload_table": ("compute", "close.read"),
    "close.read_register": ("read", "close.read"),
    "close.propose_aje": ("propose", "suggestion.create"),
    "close.plan_history_profile": ("compute", "close.read"),
}


def test_ac_the_registry_check_passes_and_every_tool_is_registered() -> None:
    import abacus.modules.agents.api  # noqa: F401 -- registers the catalogue

    assert {d.name for d in tools.AGENT_TOOLS} == set(NAMES)
    for decl in tools.AGENT_TOOLS:
        registered = registered_tools()[decl.name]
        assert (registered.kind, registered.action) == NAMES[decl.name]
        assert (PROMPTS / f"tool.{decl.name}" / "v1.txt").is_file()


def test_ac_propose_aje_only_suggests_and_code_fills_the_amount() -> None:
    lines = tools.aje_lines("unrecorded_deposit", "35", "5010", D("380.00"))
    assert [(ln.account_ref, ln.debit, ln.credit) for ln in lines] == [
        ("35", D("380.00"), D("0.00")),
        ("5010", D("0.00"), D("380.00")),
    ]
    out = tools.aje_lines("unrecorded_withdrawal", "35", "6100", D("12.50"))
    assert [(ln.account_ref, ln.debit) for ln in out] == [("6100", D("12.50")), ("35", D("0.00"))]
    with pytest.raises(NotFound):
        tools.aje_lines("outstanding_check", "35", "6100", D("1240.00"))
    decl = next(d for d in tools.AGENT_TOOLS if d.name == "close.propose_aje")
    assert decl.kind == "propose" and decl.action == "suggestion.create"
    assert "amount" not in decl.input_model.model_fields  # the model never supplies a figure


def test_untrusted_fields_are_declared_on_every_read_of_client_text() -> None:
    by_name = {d.name: d for d in tools.AGENT_TOOLS}
    assert by_name["close.read_register"].untrusted == ("lines",)
    assert by_name["close.reconcile"].untrusted == ("items",)
    assert by_name["close.read_checklist"].untrusted == ("rows",)
    assert all(d.records_read for d in tools.AGENT_TOOLS if d.kind != "propose")
