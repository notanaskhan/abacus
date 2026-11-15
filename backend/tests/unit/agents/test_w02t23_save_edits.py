"""W-02-T23 rest (TASK-8072; W-02 AC-W4, AC-W5; DEC-5058): a person's Edit... on the Save to
Files card names one of the card's folders and a usable name, and only someone who can save to
the engagement may approve it; the approved write files under the edited folder and name."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest

from abacus.ai_gateway.prompts import prompt
from abacus.modules.agents import file_tools as ft
from abacus.modules.agents import proposals

SEP = " \u203a "  # the card's separator
type _Fake = Any  # Any: proposal, row and context doubles
type _Edits = dict[int, tuple[dict[str, object], str]]


def test_saved_to_reads_the_folder_and_the_name() -> None:
    assert ft.saved_to(f"Workpapers{SEP}Season progress.xlsx") == (
        "workpapers",
        "Season progress.xlsx",
    )
    assert ft.saved_to(f"Correspondence{SEP}  Notes.xlsx ") == ("correspondence", "Notes.xlsx")


@pytest.mark.parametrize(
    "value",
    [
        "Workpapers / Season.xlsx",  # no separator
        f"Firm reports{SEP}Season.xlsx",  # not a folder the card offers
        f"Workpapers{SEP}",  # no name
        f"Workpapers{SEP}../Season.xlsx",  # a path, not a name
        f"Workpapers{SEP}{'x' * 201}",  # too long
        None,
        42,
    ],
)
def test_saved_to_refuses_anything_else(value: object) -> None:
    assert ft.saved_to(value) is None


def test_file_save_has_its_edit_validator() -> None:
    validators = proposals._EDIT_VALIDATORS  # pyright: ignore[reportPrivateUsage] -- the registry under test
    assert validators[ft.FILE_SAVE] is ft._validate_save_edit  # pyright: ignore[reportPrivateUsage] -- the validator under test


async def test_an_edit_naming_another_folder_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    proposal = cast(_Fake, type("P", (), {"engagement_id": uuid.uuid4()})())
    person = cast(
        _Fake,
        type("C", (), {"tenant": None, "tenant_id": uuid.uuid4(), "user_id": uuid.uuid4()})(),
    )

    async def resource(*_: object) -> object:
        return object()

    async def could(*_: object) -> bool:
        return True

    monkeypatch.setattr(ft, "engagement_resource", resource)
    monkeypatch.setattr(ft, "member_could", could)
    good: _Edits = {1: ({"t": "text", "v": f"Workpapers{SEP}Season.xlsx"}, "renamed")}
    await ft._validate_save_edit(person, proposal, [], good)  # pyright: ignore[reportPrivateUsage] -- the validator under test
    bad: _Edits = {1: ({"t": "text", "v": f"Firm reports{SEP}Season.xlsx"}, "moved")}
    with pytest.raises(proposals.ProposalInvalid) as refused:
        await ft._validate_save_edit(person, proposal, [], bad)  # pyright: ignore[reportPrivateUsage] -- the validator under test
    assert refused.value.facts == {"field": "saved_to"}


async def test_an_approver_who_cannot_save_there_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proposal = cast(_Fake, type("P", (), {"engagement_id": uuid.uuid4()})())
    person = cast(
        _Fake,
        type("C", (), {"tenant": None, "tenant_id": uuid.uuid4(), "user_id": uuid.uuid4()})(),
    )

    async def resource(*_: object) -> object:
        return object()

    async def could_not(*_: object) -> bool:
        return False

    monkeypatch.setattr(ft, "engagement_resource", resource)
    monkeypatch.setattr(ft, "member_could", could_not)
    edit: _Edits = {1: ({"t": "text", "v": f"Deliverables{SEP}Season.xlsx"}, "renamed")}
    with pytest.raises(proposals.ProposalInvalid) as refused:
        await ft._validate_save_edit(person, proposal, [], edit)  # pyright: ignore[reportPrivateUsage] -- the validator under test
    assert refused.value.facts == {"field": "folder_not_writable"}


def test_prompt_v2_offers_attach_only_on_the_save_question() -> None:
    v2 = prompt("workbench.assistant@v2").text
    assert "attach_only" in v2 and "Attach it to this session only" in v2
    assert "attach_only" not in prompt("workbench.assistant@v1").text  # v1 is immutable
