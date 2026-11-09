"""A-07-T26 (TASK-6311; A-07 F4; AU-C 260, 265, 703; DEC-83, DEC-3011): governance communications.

Row acceptance: "The Northwind planning letter reaches only Benefits Committee grant holders, Dana
Kowalski's management grant cannot read it (INV-4), and an acknowledgement moves the row to
Acknowledged." The reading half is the room's (R-02-T12's suite); this suite holds the service's
code: composition, the regenerate merge, the output checks and AU-C 265's due date.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import cast

import pytest

from abacus.modules.assurance import governance_comms as gc
from abacus.modules.identity.api import AuthContext

FACTS = gc.Facts(
    significant_risks=(("R1", "Contributions and remittance"), ("R4", "Participant data")),
    service_organizations=((uuid.uuid4(), "Keystone Retirement Services"),),
    deficiencies=(("F-01", "significant_deficiency"),),
    findings=("F-01", "F-02"),
)


def test_the_planning_letter_is_built_from_risks_and_service_organisations() -> None:
    sections = {s.key: s for s in gc.compose("planning_260", FACTS)}
    assert list(sections) == [
        "responsibilities", "scope_timing", "significant_risks", "service_organizations",
    ]  # fmt: skip
    assert sections["significant_risks"].built_from == ("R1", "R4")
    assert "Contributions and remittance (R1)" in sections["significant_risks"].body
    assert "Keystone Retirement Services" in sections["service_organizations"].body
    assert not any(s.human_edited for s in sections.values())


def test_the_265_letter_combines_703_and_names_concluded_deficiencies() -> None:
    sections = {s.key: s for s in gc.compose("sd_mw_265", FACTS)}
    assert set(sections) == {"deficiencies", "reportable_703"}
    assert sections["deficiencies"].body == "- F-01: a significant deficiency"
    assert gc.STANDARD["sd_mw_265"] == "AU-C 265 · 703"


def test_regenerate_keeps_a_persons_edit_and_refreshes_the_rest() -> None:
    first = gc.compose("planning_260", FACTS)
    edited = [
        gc.LetterPart(s.key, s.heading, "Our words.", s.built_from, True)
        if s.key == "responsibilities"
        else s
        for s in first
    ]
    later = gc.Facts(significant_risks=(("R7", "Loans"),))
    merged = {s.key: s for s in gc.merge(edited, gc.compose("planning_260", later))}
    assert merged["responsibilities"].body == "Our words."
    assert merged["responsibilities"].human_edited
    assert merged["significant_risks"].built_from == ("R7",)


def test_output_checks_refuse_materiality_amounts_and_sas_114() -> None:
    clean = gc.compose("planning_260", FACTS)
    assert gc.letter_checks("planning_260", clean) == []
    with_materiality = [*clean, gc.LetterPart("x", "Scope", "Planning materiality is low.")]
    assert "materiality_in_planning_letter" in gc.letter_checks("planning_260", with_materiality)
    with_amount = [*clean, gc.LetterPart("x", "Scope", "Net assets of $16,812,400.")]
    assert "amount_in_planning_letter" in gc.letter_checks("planning_260", with_amount)
    old = [gc.LetterPart("x", "Basis", "Communicated under SAS 114.")]
    assert gc.letter_checks("completion_260", old) == ["sas_114"]
    # Materiality may be discussed at completion; only the planning letter refuses it.
    assert gc.letter_checks("completion_260", with_materiality[-1:]) == []


def test_au_c_265_is_due_60_days_after_release() -> None:
    released = datetime(2026, 10, 2, 21, 0, tzinfo=UTC)
    assert gc.due_on("sd_mw_265", released) == date(2026, 12, 1)
    assert gc.due_on("sd_mw_265", None) is None
    assert gc.due_on("planning_260", released) is None


def test_the_content_hash_follows_the_sections() -> None:
    a = gc.canonical(gc.compose("planning_260", FACTS))[1]
    b = gc.canonical(gc.compose("planning_260", FACTS))[1]
    c = gc.canonical(gc.compose("planning_260", gc.Facts()))[1]
    assert a == b != c


def test_a_firm_template_opens_the_letter_in_its_own_words() -> None:
    """DEC-3027: a published governance_letter version's paragraphs, read from its C11 blocks,
    open the letter; the fact sections follow unchanged and a regenerate keeps the template."""
    blocks: list[object] = [
        {"type": "heading", "level": 1, "text": "Not a paragraph"},
        {"type": "paragraph", "runs": [
            {"type": "text", "text": "We communicate "},
            {"type": "text", "text": "the significant findings."},
        ]},
        {"type": "paragraph", "runs": [{"type": "var", "key": "client"}]},
        "not a block",
        {"type": "paragraph", "runs": [
            {"type": "text", "text": "Corrected misstatements are listed."},
        ]},
    ]  # fmt: skip
    words = gc.template_paragraphs(blocks)
    assert words == [
        "We communicate the significant findings.",
        "Corrected misstatements are listed.",
    ]
    sections = gc.compose("completion_260", FACTS, words)
    assert sections[0].key == gc.FIRM_TEMPLATE
    assert (
        sections[0].body
        == "We communicate the significant findings.\n\nCorrected misstatements are listed."
    )
    assert [s.key for s in sections[1:]] == [s.key for s in gc.compose("completion_260", FACTS)]
    assert gc.template_paragraphs(None) == []
    assert gc.compose("completion_260", FACTS, [])[0].key != gc.FIRM_TEMPLATE


class _Rows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _Session:
    """A session stand-in: the bodies owned by the engagement's client, and no recipient rows."""

    def __init__(self, owned: set[uuid.UUID]) -> None:
        self.owned = owned

    async def execute(self, _sql: object, params: dict[str, object]) -> _Rows:
        from types import SimpleNamespace

        ids = cast(list[uuid.UUID], params.get("ids", []))
        return _Rows([SimpleNamespace(id=i) for i in ids if i in self.owned])

    async def scalar(self, _sql: object, _params: dict[str, object]) -> None:
        return None


async def test_a_body_of_another_client_is_never_a_recipient_or_sent_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S32 partials review: `set_recipients` keeps to the engagement's client's bodies, and a send
    names a body set as this work item's recipient, or it is refused before any grant."""
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    ours, theirs = uuid.uuid4(), uuid.uuid4()
    session = _Session({ours})

    @asynccontextmanager
    async def tenant_session(_: object) -> AsyncGenerator[_Session]:
        yield session

    async def person(*_: object) -> uuid.UUID:
        return uuid.uuid4()

    async def ref(*_: object) -> object:
        return SimpleNamespace(client_id=uuid.uuid4())

    async def read(*_: object) -> object:
        return SimpleNamespace(
            status="awaiting_ep_approval", content_hash="h", kind="planning_260"
        )

    async def opened(*_: object) -> tuple[gc.LetterPart, ...]:
        return ()

    monkeypatch.setattr(gc, "tenant_session", tenant_session)
    monkeypatch.setattr(gc, "_person", person)
    monkeypatch.setattr(gc, "get_ref", ref)
    monkeypatch.setattr(gc, "_read", read)
    monkeypatch.setattr(gc, "_open", opened)
    ctx = cast(AuthContext, SimpleNamespace(mfa_at=datetime.now(UTC), tenant=None))
    with pytest.raises(gc.LetterCheckFailed):
        await gc.set_recipients(ctx, uuid.uuid4(), [ours, theirs])
    with pytest.raises(gc.LetterCheckFailed):
        await gc.approve_and_send(
            ctx,
            uuid.uuid4(),
            uuid.uuid4(),
            governance_body_id=theirs,
            recipient_contact_ids=[uuid.uuid4()],
            channel="governance_room",
            seen_hash="h",
        )
