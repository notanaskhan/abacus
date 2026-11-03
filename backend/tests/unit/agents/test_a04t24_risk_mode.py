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
from abacus.modules.agents.section_draft import DRAFTER, mode_call
from abacus.modules.agents.section_sources import SourcePaper, mode_mapping
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
    assert prompt == "workpapers.section_draft.risk@v1"
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
    monkeypatch.setattr(risks, "linked_ids", linked)

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
    }
    facts = dict(found.facts)
    assert facts["risks_total"] == {"t": "decimal", "v": "2"}
    assert facts["risks_unaddressed"] == {"t": "text", "v": "R8"}


def test_ac4_7_every_target_field_is_one_the_applier_takes() -> None:
    assert {f for _, f in draft_mappings.RISK_COLUMNS} <= set(risks.FIELDS)
