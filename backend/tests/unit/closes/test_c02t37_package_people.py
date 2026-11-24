"""C-02-T37 (TASK-8923; CLS-08 d, e; DEC-5925): the package read names who released it, whom
approval was requested from (the owner and the approver of record), and the client contact who
approved, each read now; nothing before release, and a reader without `client_contact.read` sees
the releaser only."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from abacus.modules.closes import package_service as ps
from abacus.modules.engagements import api as engagements_api
from abacus.modules.identity import api as identity_api

pytestmark = pytest.mark.asyncio

PRIYA, TESS, BEN, OTHER = uuid4(), uuid4(), uuid4(), uuid4()
# The rule under test, private to the service; called with stand-ins for the context and row.
people = cast(Callable[..., Awaitable[Any]], ps._people)  # pyright: ignore[reportPrivateUsage]
EMPTY = ps._People()  # pyright: ignore[reportPrivateUsage]


def _row(
    *, released: bool = True, approved_by: UUID | None = None, declined_by: UUID | None = None
) -> object:
    return SimpleNamespace(
        released_by=PRIYA if released else None,
        client_approved_by_contact_id=approved_by,
        client_declined_by_contact_id=declined_by,  # C-02-T41
    )


def _patch(monkeypatch: pytest.MonkeyPatch, *, contacts: object) -> None:
    async def names_of(ids: list[UUID]) -> dict[UUID, str]:
        return {PRIYA: "Priya Raman"} if PRIYA in ids else {}

    async def engagement_contacts(_ctx: object, _e: object) -> object:
        if isinstance(contacts, Exception):
            raise contacts
        return contacts

    async def client_contact_names(_t: object, _e: object, ids: list[UUID]) -> dict[UUID, str]:
        known = {TESS: "Tess Moreno", BEN: "Ben Ashby", OTHER: "Lee Park"}
        return {i: known[i] for i in ids if i in known}

    monkeypatch.setattr(identity_api, "names_of", names_of)
    monkeypatch.setattr(engagements_api, "engagement_contacts", engagement_contacts)
    monkeypatch.setattr(engagements_api, "client_contact_names", client_contact_names)


async def test_ac_d_released_by_and_approval_requested_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, contacts=[
        SimpleNamespace(contact_id=TESS, designation="owner"),
        SimpleNamespace(contact_id=BEN, designation="approver_of_record"),
        SimpleNamespace(contact_id=OTHER, designation="bookkeeper"),
    ])  # fmt: skip
    found = await people(SimpleNamespace(tenant=None), uuid4(), _row())
    assert (found.released_by, found.requested_from, found.client_approved_by) == (
        "Priya Raman", ("Tess Moreno", "Ben Ashby"), None,
    )  # fmt: skip


async def test_ac_e_the_approving_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, contacts=[SimpleNamespace(contact_id=TESS, designation="owner")])
    found = await people(SimpleNamespace(tenant=None), uuid4(), _row(approved_by=TESS))
    assert found.client_approved_by == "Tess Moreno"


async def test_ac_nothing_before_release_and_no_names_without_contact_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.identity.api import Forbidden

    _patch(monkeypatch, contacts=Forbidden("client_contact.read", "role"))
    assert await people(SimpleNamespace(tenant=None), uuid4(), _row(released=False)) == EMPTY
    found = await people(SimpleNamespace(tenant=None), uuid4(), _row())
    assert (found.released_by, found.requested_from) == ("Priya Raman", ())


async def test_c02t41_the_declining_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-02-T41 (DEC-5927): POR-08 c's decline names the client contact who declined."""
    _patch(
        monkeypatch, contacts=[SimpleNamespace(contact_id=BEN, designation="approver_of_record")]
    )
    found = await people(SimpleNamespace(tenant=None), uuid4(), _row(declined_by=BEN))
    assert found.client_declined_by == "Ben Ashby"
