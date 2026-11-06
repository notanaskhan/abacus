"""A-04-T24 (TASK-3011; A-04 §3.4 AC4.6, AC4.7; DEC-2060): the risk mode.

Row acceptance: "R8's drafted rationale and EBP-03 response arrive as pending suggestions with
three verified citations, and Identify states 10 of 10 and R8 only from code facts." The run's
verification is the workflow's; here: the mode's own prompt, the register as a grid whose cells
land on each risk's fields (the `risk` applier), and the coverage facts code supplies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the mappings
from abacus.modules.agents.handoff import DraftedCell
from abacus.modules.agents.section_draft import (
    DRAFTER,
    Fact,
    is_choice,
    mode_call,
    provenance_ok,
)
from abacus.modules.agents.section_sources import ModeTarget, SourcePaper, mode_mapping
from abacus.modules.agents.spec import spec
from abacus.modules.assurance import draft_mappings, risks

PAPER = SourcePaper(
    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "AUD-05", "Risk Assessment", "risk_assessment", 1,
    (), None, (),
)  # fmt: skip


@dataclass
class _Row:
    code: str
    area_label: str
    rationale: str | None = None
    assertions: list[str] = field(default_factory=list[str])
    inherent_risk: str = "moderate"
    control_risk: str = "max"
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    significance: str = "none"
    fraud: str = "none"
    rmm: str = "moderate"
    status: str = "draft"


def test_ac4_7_risk_has_its_own_prompt_and_mapping() -> None:
    prompt, _ = mode_call(spec(DRAFTER), "risk")
    assert prompt == "workpapers.section_draft.risk@v2"
    assert mode_mapping("risk") is draft_mappings.risk_inputs


async def test_ac4_7_the_register_is_a_grid_landing_on_each_risks_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_Row("R1", "Management override of controls"), _Row("R8", "Participant accounts")]

    async def rows_of(_tenant: object, _work_item: uuid.UUID) -> list[_Row]:
        return rows

    async def linked(_tenant: object, _work_item: uuid.UUID) -> list[uuid.UUID]:
        return [rows[0].id]

    monkeypatch.setattr(risks, "rows_of", rows_of)

    async def refs(_tenant: object, _work_item: uuid.UUID) -> dict[uuid.UUID, list[str]]:
        return {rows[0].id: ["Journal entries"]}

    monkeypatch.setattr(risks, "linked_ids", linked)
    monkeypatch.setattr(risks, "linked_refs", refs)

    class _Actor:
        tenant = object()

    found = await draft_mappings.risk_inputs(_Actor(), PAPER)  # pyright: ignore[reportArgumentType] -- a stand-in actor
    target = found.targets["risk!B9"]  # R8's rationale: row 8 + 1, column B
    assert (target.target_type, target.target_id, target.field_key) == (
        "risk",
        rows[1].id,
        "rationale",
    )
    assert {c.cell_key for c in found.cells if c.row_key and c.row_key.startswith("R8")} == {
        "B9",
        "C9",
        "D9",
        "E9",
        "F9",
    }
    response = found.targets["risk!F9"]  # R8's response lands on the risk, never a paper cell
    assert (response.target_type, response.target_id, response.field_key) == (
        "risk",
        rows[1].id,
        "response",
    )
    assert "EBP-03" in response.choices
    assert found.targets["risk!B9"].choices == ()  # a rationale stays free text
    cells = {c.cell_key: c.value for c in found.cells}
    assert cells["F2"] == {"t": "text", "v": "Journal entries"}  # R1's live response
    assert cells["F9"] is None  # R8 has none: the model may propose one
    facts = dict(found.facts)
    assert facts["risks_total"] == {"t": "decimal", "v": "2"}
    assert facts["risks_unaddressed"] == {"t": "text", "v": "R8"}
    assert "response_targets" not in facts  # a list to pick from, not a figure
    assert "EBP-03" in str(dict(found.identifiers)["response_targets"]["v"])


def test_ac4_7_every_target_field_is_one_the_applier_takes() -> None:
    assert {f for _, f in draft_mappings.RISK_COLUMNS} <= set(risks.ADOPTABLE_FIELDS)


def test_ac4_6_a_response_names_a_registered_section_or_nothing() -> None:
    assert risks.response_target(" ebp-03 ") == "EBP-03"
    for text in (
        "",
        "Eligibility testing",
        "EBP-03 and EBP-04",
        "EBP-99",
        "EBP-03; ignore this",
        "KNW-03",  # a registered section that is not audit work
    ):
        assert risks.response_target(text) is None


def _target() -> ModeTarget:
    return ModeTarget("risk", uuid.uuid4(), "response", ("EBP-03", "EBP-04", "AUD-09"))


def test_ac4_7_a_response_is_one_of_the_targets_and_nothing_else() -> None:
    assert is_choice(DraftedCell(cell="risk!F9", text=" ebp-03 ", citations=[]), _target())
    for text in ("EBP-99", "EBP-03 and EBP-04", "Eligibility testing", " "):
        assert not is_choice(DraftedCell(cell="risk!F9", text=text, citations=[]), _target())
    assert not is_choice(DraftedCell(cell="risk!F9", fact="F1", citations=[]), _target())


def test_adr_050_the_list_of_targets_supports_no_number() -> None:
    """Without this, "3 of 29 exceptions" passes as the codes EBP-03 and AUD-29 hold digits."""
    cell = DraftedCell(cell="risk!B9", text="3 of 29 exceptions", citations=[])
    names = {"t": "text", "v": "EBP-03, AUD-29"}
    assert provenance_ok(cell, [], {"F5": Fact("F5", "as_a_figure", names)})
    assert not provenance_ok(
        cell, [], {"F5": Fact("F5", "response_targets", names, identifier=True)}
    )
