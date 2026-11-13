"""T-05-T37 rest (TASK-7634; DEC-4629): TXP-02's line picker (e2) over the published set, and a
person's pick: the tax reviewer's maps the account as that person (human, audited); a preparer's
raises a review note proposing the line and maps nothing; a key outside the set is refused before
either. Proposals stay the agent's (ADR-161)."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.modules.ledger.api import FormLineKeyUnknown
from abacus.modules.tax import entity_mapping as em

RETURN = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()
USER = uuid.uuid4()


def _line(key: str, schedule: str, line: str, label: str, mappable: bool = True) -> Any:  # noqa: ANN401 -- a published line stand-in
    return SimpleNamespace(key=key, schedule=schedule, line=line, label=label, mappable=mappable)


LINES = SimpleNamespace(
    lines=(
        _line("L5", "L", "5", "Tax-exempt securities"),
        _line("L13", "L", "13", "Other assets"),
        _line("L14", "L", "14", "Total assets", mappable=False),
        _line("8825 Rents", "8825", "2", "Gross rents"),
    ),
    mappable_keys=frozenset({"L5", "L13", "8825 Rents"}),
    reference_set_version_id=uuid.uuid4(),
)


Facts = dict[str, Any]  # Any: write and note facts as the stand-ins received them
Recorded = tuple[str, Any]  # Any: an audit event's facts


@dataclass
class _Tx:
    recorded: list[Recorded] = field(default_factory=list[Recorded])

    def record(self, code: str, **kw: Any) -> None:  # noqa: ANN401 -- the audit facts
        self.recorded.append((code, kw))


@dataclass
class _World:
    reviewer: bool
    tx: _Tx = field(default_factory=_Tx)
    edits: list[Facts] = field(default_factory=list[Facts])
    notes: list[Facts] = field(default_factory=list[Facts])


def _ctx() -> Any:  # noqa: ANN401 -- an AuthContext stand-in
    return SimpleNamespace(tenant=SimpleNamespace(tenant_id=uuid.uuid4()), tenant_id=uuid.uuid4(),
                           user_id=USER)  # fmt: skip


def _patch(monkeypatch: pytest.MonkeyPatch, world: _World) -> None:
    @asynccontextmanager
    async def session(_t: object):  # noqa: ANN202
        async def execute(*_a: object, **_k: object) -> Any:  # noqa: ANN401
            return SimpleNamespace(first=lambda: SimpleNamespace(form="1065", tax_year=2025))

        yield SimpleNamespace(execute=execute)

    async def lines_for(*_a: object, **_k: object) -> Any:  # noqa: ANN401
        return LINES

    async def today(*_a: object) -> date:
        return date(2026, 9, 14)

    async def resource(*_a: object) -> Any:  # noqa: ANN401
        return SimpleNamespace(work_item_id=None)

    async def could(_t: object, user: object, action: str, _r: object) -> bool:
        assert (user, action) == (USER, em.APPROVE)
        return world.reviewer

    async def note(_ctx: object, target: str, target_id: object, **kw: Any) -> Any:  # noqa: ANN401
        world.notes.append({"target": target, "target_id": target_id, **kw})
        return SimpleNamespace(note=SimpleNamespace(id=uuid.UUID(int=7)))

    async def tbs(*_a: object) -> list[Any]:  # Any: trial-balance stand-ins
        return [SimpleNamespace(id=uuid.uuid4(), period_end=date(2025, 12, 31))]

    @asynccontextmanager
    async def unit(_t: object):  # noqa: ANN202
        yield world.tx

    async def ensure(_tx: object, **_k: object) -> uuid.UUID:
        return uuid.UUID(int=1)

    async def record_line(_tx: object, **kw: Any) -> None:  # noqa: ANN401
        world.edits.append(kw)

    monkeypatch.setattr(em, "tenant_session", session)
    monkeypatch.setattr(em, "tax_form_lines_for", lines_for)
    monkeypatch.setattr(em, "today", today)
    monkeypatch.setattr(em, "engagement_resource", resource)

    def same(r: object, **_k: object) -> object:
        return r

    monkeypatch.setattr(em, "replace", same)
    monkeypatch.setattr(em, "member_could", could)
    monkeypatch.setattr(em, "raise_review_note", note)
    monkeypatch.setattr(em, "engagement_trial_balances", tbs)
    monkeypatch.setattr(em, "uow", unit)
    monkeypatch.setattr(em, "ensure_tax_mapping_set", ensure)
    monkeypatch.setattr(em, "record_form_line", record_line)


def _pick(key: str = "L13") -> em.PickOutcome:
    return asyncio.run(em.pick_form_line(_ctx(), RETURN, ENGAGEMENT, "1300", key, None))


def test_ac3_4_the_picker_lists_mappable_lines_and_filters_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, _World(reviewer=True))
    every = asyncio.run(em.form_line_choices(_ctx(), "1065", 2025, None))
    assert [(c.key, c.label) for c in every] == [
        ("L5", "Schedule L · line 5 Tax-exempt securities"),
        ("L13", "Schedule L · line 13 Other assets"),
        ("8825 Rents", "Form 8825 · line 2 Gross rents"),
    ]  # the total (L14) is computed, never offered
    found = asyncio.run(em.form_line_choices(_ctx(), "1065", 2025, "exempt"))
    assert [c.key for c in found] == ["L5"]


def test_ac3_4_no_published_set_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _World(reviewer=True))

    async def none(*_a: object, **_k: object) -> Any:  # noqa: ANN401
        raise LookupError("tax_form_lines:1065:2031")

    monkeypatch.setattr(em, "tax_form_lines_for", none)
    with pytest.raises(em.NotFound):
        asyncio.run(em.form_line_choices(_ctx(), "1065", 2031, None))


def test_ac3_4_the_tax_reviewers_pick_maps_the_account_as_that_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(reviewer=True)
    _patch(monkeypatch, world)
    out = _pick()
    assert out == em.PickOutcome("mapped", mapping_set_id=uuid.UUID(int=1))
    assert len(world.edits) == 1
    edit = world.edits[0]
    assert (edit["account_code"], edit["form_line_key"], edit["edited_by"]) == (
        "1300",
        "L13",
        USER,
    )
    assert [code for code, _kw in world.tx.recorded] == ["tax.mapping_recorded"]
    assert world.notes == []


def test_ac3_4_a_preparers_pick_proposes_the_line_and_maps_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(reviewer=False)
    _patch(monkeypatch, world)
    out = _pick()
    assert out == em.PickOutcome("flagged", uuid.UUID(int=7))
    assert world.edits == [] and world.tx.recorded == []
    assert world.notes[0]["anchor_kind"] == "field"
    assert world.notes[0]["anchor_ref"] == "account:1300"
    assert "L13" in world.notes[0]["body"]


def test_ac3_4_a_key_outside_the_published_set_is_refused_before_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for reviewer in (True, False):
        world = _World(reviewer=reviewer)
        _patch(monkeypatch, world)
        with pytest.raises(FormLineKeyUnknown):
            _pick("L14")  # a total
        assert world.edits == [] and world.notes == []
