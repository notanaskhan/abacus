"""R-02-T16 (TASK-6514; SPEC-646 AC-29, AC-30; DEC-3114; DEC-93): governance room part 2.

Row acceptance: "Victoria Lam's two inquiry answers are readable only by the audit team, never by
Robert Haines and never by Dana Kowalski under either of her grants."
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.assurance import governance_room as gr

pytestmark = pytest.mark.asyncio
ROOM = uuid.uuid4()
VICTORIA, ROBERT = uuid.uuid4(), uuid.uuid4()
QUESTIONNAIRE = uuid.uuid4()


def _db(monkeypatch: pytest.MonkeyPatch, addressed_to: uuid.UUID) -> None:
    @asynccontextmanager
    async def session(_t: object) -> AsyncIterator[object]:
        async def execute(_q: object, params: dict[str, list[uuid.UUID]]) -> object:
            mine = [c for c in params["contacts"] if c == addressed_to]
            rows = [
                SimpleNamespace(questionnaire_id=QUESTIONNAIRE, respondent_contact_id=c)
                for c in mine
            ]
            return SimpleNamespace(all=lambda: rows)

        yield SimpleNamespace(execute=execute)

    async def questionnaire(_ctx: object, qid: uuid.UUID, **_k: object) -> object:
        questions = (
            SimpleNamespace(id=uuid.uuid4(), client_wording="Are you aware of any fraud?"),
            SimpleNamespace(id=uuid.uuid4(), client_wording="Have there been any allegations?"),
        )
        return SimpleNamespace(id=qid, questions=questions)

    monkeypatch.setattr(gr, "tenant_session", session)
    monkeypatch.setattr("abacus.modules.requests.api.portal_questionnaire", questionnaire)


async def test_victoria_reads_her_two_inquiries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def member(_ctx: object, _room: uuid.UUID) -> list[uuid.UUID]:
        return [VICTORIA]

    _db(monkeypatch, VICTORIA)
    monkeypatch.setattr(gr, "_open", member)
    found = await gr.room_inquiries(SimpleNamespace(tenant=None), ROOM)  # type: ignore[arg-type]  # double
    assert [i.questionnaire_id for i in found] == [QUESTIONNAIRE, QUESTIONNAIRE]


async def test_robert_a_member_sees_none_of_them(monkeypatch: pytest.MonkeyPatch) -> None:
    async def member(_ctx: object, _room: uuid.UUID) -> list[uuid.UUID]:
        return [ROBERT]

    _db(monkeypatch, VICTORIA)
    monkeypatch.setattr(gr, "_open", member)
    assert await gr.room_inquiries(SimpleNamespace(tenant=None), ROOM) == []  # type: ignore[arg-type]  # double


async def test_a_non_member_like_dana_gets_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def not_member(_ctx: object, _room: uuid.UUID) -> list[uuid.UUID]:
        raise NotFound(gr.ROOM)

    monkeypatch.setattr(gr, "_open", not_member)
    with pytest.raises(NotFound):
        await gr.room_inquiries(SimpleNamespace(tenant=None), ROOM)  # type: ignore[arg-type]  # double
    with pytest.raises(NotFound):
        await gr.room_reports(SimpleNamespace(tenant=None), ROOM)  # type: ignore[arg-type]  # double
