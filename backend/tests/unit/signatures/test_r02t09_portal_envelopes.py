"""R-02-T09 close (S31; TASK-6229; DEC-2824): POR-09's "In Sign" rows.

A client person sees their own envelopes on a work item: out for signature reads `in_sign`, one
they signed reads `signed`; a firm user and a person with no contact see none.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import abacus.modules.signatures.api as signatures_api
from abacus.kernel.db import TenantContext
from abacus.modules.identity.context import AuthContext
from abacus.modules.reporting import deliverables
from abacus.modules.signatures import signer_facts as sf


def _ctx(*, client: bool = True) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
        client=client,
    )


class _Session:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_a: object, **_k: object) -> SimpleNamespace:
        rows = self.rows

        def everything() -> list[SimpleNamespace]:
            return rows

        return SimpleNamespace(all=everything)


def _rows(monkeypatch: pytest.MonkeyPatch, rows: list[SimpleNamespace], contacts: int = 1) -> None:
    async def mine(_t: object, _u: object) -> set[uuid.UUID]:
        return {uuid.uuid4() for _ in range(contacts)}

    def open_session(_t: object) -> _Session:
        return _Session(rows)

    monkeypatch.setattr(sf, "contact_ids_of_user", mine)
    monkeypatch.setattr(sf, "tenant_session", open_session)


async def test_out_for_signature_is_in_sign_and_signed_is_signed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    letter, gov = uuid.uuid4(), uuid.uuid4()
    _rows(
        monkeypatch,
        [
            SimpleNamespace(id=letter, title="Representation letter", source_kind="rep_letter",
                            envelope_status="sent", signer_status="pending"),
            SimpleNamespace(id=gov, title="AU-C 260 letter", source_kind="governance_letter",
                            envelope_status="completed", signer_status="signed"),
        ],
    )  # fmt: skip
    found = await sf.portal_envelopes(_ctx(), uuid.uuid4())
    assert [(e.envelope_id, e.kind, e.status) for e in found] == [
        (letter, "other", "in_sign"),
        (gov, "governance_letter", "signed"),
    ]


async def test_a_firm_user_or_a_person_with_no_contact_sees_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _rows(monkeypatch, [SimpleNamespace(id=uuid.uuid4())], contacts=0)
    assert await sf.portal_envelopes(_ctx(), uuid.uuid4()) == []
    assert await sf.portal_envelopes(_ctx(client=False), uuid.uuid4()) == []


def test_the_rail_has_the_envelope_rows_registered() -> None:
    assert signatures_api is not None
    assert deliverables._ENVELOPE_ROWS  # pyright: ignore[reportPrivateUsage]  # the slot under test
