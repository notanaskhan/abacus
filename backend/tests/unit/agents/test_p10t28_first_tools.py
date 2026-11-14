"""P-10-T28 (TASK-6605; C17; ADR-233, ADR-049, ADR-050): the first tools are registered from their
owning modules with registry description prompts, read at most 200 rows that carry ids, and
compute their totals in code. Runtime refusals (walls, `client_scope`) are P-10-T31's suite."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.ai_gateway.prompts import prompt
from abacus.modules.agents.api import registered_tools
from abacus.modules.agents.tools.catalogue import DECLARED
from abacus.modules.agents.tools.registry import MAX_ROWS, row_fields
from abacus.modules.evidence.agent_tools import roll_forward
from abacus.modules.identity.api import RULES
from abacus.modules.ledger.agent_tools import change_pct

FIRST = {
    "engagements.list", "engagements.read", "engagements.read_graph", "engagements.read_team",
    "requests.list_items", "requests.read_item", "evidence.search", "evidence.read_extraction",
    "evidence.list_uploads", "knowledge.search", "methodology.read_step", "activity.read",
    "ledger.read_tb", "ledger.compare_periods", "ledger.tie_out",
}  # fmt: skip


def test_the_fifteen_first_tools_are_registered() -> None:
    assert set(registered_tools()) >= FIRST
    # P-10-T38 adds the files tools beside the fifteen (compute, propose and approved_write).
    files = {"files.build_workbook", "files.propose_save", "files.save_approved"}
    # W-02-T11 (DEC-4716) declares `binders.read` beside requests' first tools.
    workbench = {"binders.read"}
    # W-02-T19 (DEC-4930): the offices read the season plan groups by.
    workbench |= {"identity.list_offices", "files.list_folders"}
    assert {d.name for d in DECLARED} == FIRST | files | workbench


@pytest.mark.parametrize("name", sorted(FIRST))
def test_each_has_a_registry_description_prompt(name: str) -> None:
    found = registered_tools()[name]
    assert found.description == f"tool.{name}@v1"
    assert prompt(found.description).text.strip()


@pytest.mark.parametrize("name", sorted(FIRST))
def test_each_reads_or_computes_with_ids_and_at_most_200_rows(name: str) -> None:
    found = registered_tools()[name]
    assert found.kind in ("read", "compute")
    assert found.max_rows <= MAX_ROWS
    for field, row in row_fields(found.output_model).items():
        assert "id" in row.model_fields, (name, field)
        limit = found.output_model.model_fields[field].metadata
        assert any(getattr(m, "max_length", None) == MAX_ROWS for m in limit), (name, field)


@pytest.mark.parametrize("name", sorted(FIRST))
def test_the_agent_holds_each_action_only_through_task_scope(name: str) -> None:
    assert RULES[registered_tools()[name].action].decisions.get("agent") == "task_scope"


def test_client_content_is_wrapped_untrusted() -> None:
    tools = registered_tools()
    assert "lines" in tools["ledger.read_tb"].untrusted
    assert "passages" in tools["knowledge.search"].untrusted
    assert {"still_needed", "na_note"} <= set(tools["requests.read_item"].untrusted)
    assert "entity_name" in tools["evidence.read_extraction"].untrusted


def test_code_computes_the_roll_forward_and_the_change() -> None:
    d = Decimal
    assert roll_forward(d("100.00"), d("50.00"), d("30.00"), d("120.00")) == d("0.00")
    assert roll_forward(d("100.00"), None, d("30.00"), d("120.00")) is None
    assert change_pct(d("110.00"), d("100.00")) == d("10.0")
    assert change_pct(d("5.00"), d("0.00")) is None
    assert change_pct(d("-90.00"), d("-100.00")) == d("10.0")
