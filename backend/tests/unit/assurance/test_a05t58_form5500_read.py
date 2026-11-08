"""A-05-T58 (TASK-6214; A-05 F7; EBP-07): the Form 5500 read is the server's tie-out, not a stub.

Row acceptance: "Typed form values render in #6A98E8, one matchId lights row and field together,
and the empty state shows until Summit's draft arrives." The server's half: no draft reads
`draft_received = false`; each row carries both sides, the code's difference and classification,
and the cited region's own match id (C4 §3.1; INV-2), never one the screen composes.
"""

from __future__ import annotations

from decimal import Decimal as D
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.assurance import ebp_contract
from abacus.modules.assurance.ebp_form5500 import Form5500View, LineView, PartIvView

WI = uuid4()
VERSION = uuid4()
CITED = uuid4()
HIDDEN = uuid4()
MATCH = f"ev:{VERSION}#p2:72,410,540,424"


async def _open(*_: object) -> None:
    return None


def _line(code: str, fs: str, form: str | None, kind: str, citation: UUID | None) -> LineView:
    off = D(fs) - D(form or "0")
    return LineView(
        uuid4(), code, code, D(fs), None if form is None else D(form), off or None, kind,
        "Note 8" if off else None, citation,
    )  # fmt: skip


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Form5500View]:
    holder: dict[str, Form5500View] = {}

    async def view(_ctx: object, _wi: UUID) -> Form5500View:
        return holder["view"]

    async def citation(_ctx: object, citation_id: UUID) -> SimpleNamespace:
        if citation_id == HIDDEN:
            raise NotFound("citation")
        return SimpleNamespace(match_id=MATCH)

    monkeypatch.setattr(ebp_contract, "_gate", _open)
    monkeypatch.setattr(ebp_contract, "form5500_view", view)
    monkeypatch.setattr(ebp_contract, "citation_display", citation)
    return holder


async def test_no_draft_reads_not_received(wired: dict[str, Form5500View]) -> None:
    wired["view"] = Form5500View(None, None, (), ())
    out = await ebp_contract.ebp_form5500_route(WI, None)  # type: ignore[arg-type]  # a test double or a private name the test pins
    assert out.draft_received is False
    assert out.rows == [] and out.part_iv == [] and out.evidence_version_id is None


async def test_rows_carry_both_sides_and_the_citations_match_id(
    wired: dict[str, Form5500View],
) -> None:
    wired["view"] = Form5500View(
        uuid4(),
        VERSION,
        (
            _line("1b(2)", "33540", None, "reconciling_item", None),
            _line("1c(9)", "1163480", "1163480", "tie", HIDDEN),
            _line("1l", "16861000", "16812400", "reconciling_item", CITED),
        ),
        (PartIvView("4a", "yes", D("33540"), "EBP-04 finding", "consistent", None),),
    )
    out = await ebp_contract.ebp_form5500_route(WI, None)  # type: ignore[arg-type]  # a test double or a private name the test pins
    assert out.draft_received is True and out.evidence_version_id == VERSION
    rows = {r.line_code: r for r in out.rows}
    assert rows["1l"].difference == D("48600") and rows["1l"].match_id == MATCH
    assert rows["1l"].f5500_amount == D("16812400") and rows["1l"].fs_amount == D("16861000")
    # A citation the reader can't see lights nothing; an uncited line has no match.
    assert rows["1c(9)"].match_id is None and rows["1b(2)"].match_id is None
    assert (
        rows["1b(2)"].classification == "reconciling_item" and rows["1b(2)"].note_ref == "Note 8"
    )
    [answer] = out.part_iv
    assert answer.line == "4a" and answer.draft_answer == "yes"
    assert answer.basis == "EBP-04 finding" and answer.consistency == "consistent"


async def test_an_inconsistent_4a_and_a_na_answer(wired: dict[str, Form5500View]) -> None:
    wired["view"] = Form5500View(
        uuid4(),
        VERSION,
        (),
        (
            PartIvView("4a", "no", None, None, "inconsistent", uuid4()),
            PartIvView("4j", "na", None, None, None, None),
            PartIvView("4e", "yes", D("500000"), None, None, None),
        ),
    )
    out = await ebp_contract.ebp_form5500_route(WI, None)  # type: ignore[arg-type]  # a test double or a private name the test pins
    by_line = {a.line: a for a in out.part_iv}
    assert by_line["4a"].consistency == "inconsistent" and by_line["4a"].basis == ""
    assert by_line["4j"].draft_answer is None
    assert "4e" not in by_line  # the contract's five lines only (4i and 4a schedules; DEC-2814)
