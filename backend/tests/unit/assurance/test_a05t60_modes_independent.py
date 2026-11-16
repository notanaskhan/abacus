"""A-05-T55 and A-05-T56 (A-05-T60, TASK-6217; ADR-078): independent AC tests for the
`ebp_form5500` and `related_parties` modes.

Written from the rows and A-05 F9/F11, not the modes' own tests. Row acceptance: "No agent path
records a classification, a conclusion or a screen-out, and sealed names never leave the
database." Covered: the agent principal is denied every action that classifies a Form 5500 line,
concludes an estimate or screens a related party out; the drafter carries no tools, so a mode's
output is a C3 suggestion and nothing else; the mode modules only read and never import a write;
a related party's sealed name is never selected by any read, and the related-parties mode's inputs
carry no names as facts.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import cast

import pytest

from abacus.modules.agents.api import registered_tools
from abacus.modules.agents.specs._specs import SPECS
from abacus.modules.identity.authz import matrix

SRC = Path(__file__).resolve().parents[3] / "src" / "abacus"
ASSURANCE = SRC / "modules" / "assurance"
MODES = ("ebp_form5500_mode.py", "related_parties_mode.py")

# Every human act the two modes border: classify or key a line, send its note, conclude an
# estimate, add, screen out or manage a party, decide a card.
HUMAN_ONLY = (
    "ebp_form5500.key",
    "ebp_form5500.send_note",
    "estimate.evaluate",
    "estimate.request_conclusion",
    "related_party.manage",
    "related_party.screen_out",
    "party_in_interest.manage",
    "decision.decide",
)


@pytest.mark.parametrize("action", HUMAN_ONLY)
def test_the_agent_is_denied_every_recording_act(action: str) -> None:
    assert matrix.ACTIONS[action].get("agent", "deny") == "deny", action
    assert matrix.ACTIONS[action].get("system", "deny") == "deny", action


def test_the_drafter_has_no_tools_so_a_mode_only_suggests() -> None:
    # A-08-T23 (S47) gave the drafter its first tools. The guarantee is unchanged: every tool
    # only reads or computes, or proposes through `suggestion.create`; none writes anything else.
    spec = SPECS["workpapers.section_drafter"]
    tools = registered_tools()
    listed = spec.get("tools", [])
    assert isinstance(listed, list)
    for name in [str(t) for t in cast("list[object]", listed)]:
        found = tools[name]
        assert found.kind in {"read", "compute", "propose"}, name
        if found.kind == "propose":
            assert found.action == "suggestion.create", name
    modes = spec["modes"]
    assert isinstance(modes, dict)
    names: set[str] = {str(k) for k in modes}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]  # a test double or a private name the test pins
    assert {"ebp_form5500", "related_parties"} <= names


def _code_names(source: str) -> set[str]:
    """Every name and attribute the module's code uses (its docstrings may name a write)."""
    tree = ast.parse(source)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {
        alias.name.rsplit(".", 1)[-1]
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom | ast.Import)
        for alias in n.names
    }
    return names


def _sql(source: str) -> str:
    tree = ast.parse(source)
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "text"
    ]  # fmt: skip
    return " ".join(
        a.value
        for c in calls
        for a in c.args
        if isinstance(a, ast.Constant) and isinstance(a.value, str)
    )


@pytest.mark.parametrize("name", MODES)
def test_a_mode_module_only_reads(name: str) -> None:
    source = (ASSURANCE / name).read_text()
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE)\b", _sql(source)), name
    used = _code_names(source)
    for write in (
        "document_reconciling_item",
        "screen_out",
        "request_conclusion",
        "add_related_party",
        "record_finding",
        "unit_of_work",
        "uow",
    ):
        assert write not in used, (name, write)


# Reads of a sealed name that is not a related party's, each reviewed. T-07-T12 (DEC-5055): the
# trust's settlor on TXT-01's profile, opened only under `instrument.read`.
NOT_A_RELATED_PARTY = frozenset(
    {
        "modules/tax/instruments/repository.py",  # T-07-T07: moved
        # S46: a confirmation's respondent (A-08-T16) and a gift's donee (T-07-T22), sealed and
        # opened for their own pages; neither is a related party's name.
        "modules/assurance/confirmations_service.py",
        "modules/tax/estate_service.py",
        # S47 (A-08-T16/T17): the confirmation lifecycle and the respondent page open the same
        # respondent's name; neither is a related party's.
        "modules/assurance/confirmations_lifecycle.py",
        "modules/assurance/confirmations_respondent.py",
    }
)


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_no_read_selects_a_related_party_s_sealed_name() -> None:
    hits = [
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if re.search(r"SELECT[^;]*name_sealed", p.read_text(), flags=re.S)
    ]
    assert [h for h in hits if h not in NOT_A_RELATED_PARTY] == []


def test_the_related_parties_read_answers_display_refs_not_names() -> None:
    source = (ASSURANCE / "aud27.py").read_text()
    select = re.search(r"_PARTIES = text\((.*?)\)\n", source, flags=re.S)
    assert select is not None
    assert "display_ref" in select.group(1)
    assert "name" not in select.group(1).replace("display_ref", "")


def test_the_related_parties_mode_hands_the_model_no_facts() -> None:
    source = (ASSURANCE / "related_parties_mode.py").read_text()
    assert "facts=()" in source


def test_the_form5500_mode_hands_code_s_numbers_by_name() -> None:
    from decimal import Decimal

    from abacus.modules.assurance.ebp_form5500_mode import difference_facts

    facts = dict(difference_facts([("1b(2)", Decimal("48600"))], Decimal("33540")))
    assert facts == {
        "diff.1b(2)": {"t": "decimal", "v": "48600"},
        "late_deposits_4a": {"t": "decimal", "v": "33540"},
    }
