"""C-02-T40 (TASK-8924; POR-16 write-grant consent v2; DF-19; ADR-344 §6; DEC-5926).

Row acceptance: "Tess Moreno grants and revokes the write scope with fresh MFA and sees 'Posted 6
journal entries · batch 2026-08-A' in the details drawer." Here: the posting scope appears on a
live ledger card only when the catalogue declares the consent and the firm holds W1; an attest
client reads `read_only` with no consent and no control; a non-attest client reads `offered` with
the catalogue's consent v2, then `granted` with who granted it; only a person holding the grant
action may change it; the drawer's write log lists each posted batch and the closing date the
firm set, newest first. The grant itself (fresh MFA, consent version, attest refusal) is
C-02-T25's `w1_switches.grant_write`, exercised by AC suite 2 (C-02-T36).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import yaml

from abacus.modules.integrations import client_connect as cc
from abacus.modules.integrations import connect_catalog
from abacus.modules.integrations import ledger_console as lc
from abacus.modules.integrations import w1_switches as w1
from abacus.modules.integrations.catalog_import import CatalogDocumentV2
from abacus.modules.organisations import api as organisations_api

pytestmark = pytest.mark.asyncio

TESS = uuid4()
SEP14_1022 = datetime(2026, 9, 14, 15, 22, tzinfo=UTC)
write_scope = cast(Callable[..., Awaitable[Any]], cc._write_scope)  # pyright: ignore[reportPrivateUsage]
writes = cast(Callable[..., Awaitable[Any]], cc._writes)  # pyright: ignore[reportPrivateUsage]


CATALOGUE = Path(connect_catalog.__file__).parents[2].parent / "abacus_tools" / "catalogue"


def _consent() -> dict[str, object]:
    raw = yaml.safe_load((CATALOGUE / "connect_v2.yaml").read_text())
    doc = CatalogDocumentV2.model_validate(raw)
    row = next(r for r in doc.rows if r.key == "quickbooks_online")
    assert row.detail_copy.write_consent is not None
    return row.detail_copy.write_consent.model_dump()


def _entry() -> object:
    return SimpleNamespace(row=SimpleNamespace(connector_provider="quickbooks_online"))


def _live() -> object:
    return SimpleNamespace(id=uuid4(), status="active")


class _Ref:
    def resource(self) -> object:
        return object()


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    consent: object = "catalogue",
    enabled: bool = True,
    released: bool = True,
    attest: bool | None = False,
    grant: w1.LatestGrant | None = None,
    may: tuple[str, ...] = ("connection.grant_write", "connection.revoke_write"),
) -> None:
    async def write_consent_of(_s: object, _p: str) -> object:
        return _consent() if consent == "catalogue" else consent

    async def firm_switch(_t: object) -> w1.Switch:
        return w1.Switch(enabled, released, None, None)

    async def client_of_entity(_t: object, _e: object) -> UUID:
        return uuid4()

    async def attest_client_of(_t: object, _c: object) -> bool | None:
        return attest

    async def latest_grant(_t: object, _c: object) -> w1.LatestGrant | None:
        return grant

    async def get_ref(_ctx: object, _e: object) -> _Ref:
        return _Ref()

    async def allowed_actions(_ctx: object, _r: object, _a: object) -> set[str]:
        return set(may)

    async def names_of(ids: list[UUID]) -> dict[UUID, str]:
        return {TESS: "Tess Moreno"} if TESS in ids else {}

    class _Session:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(connect_catalog, "write_consent_of", write_consent_of)
    monkeypatch.setattr(w1, "firm_switch", firm_switch)
    monkeypatch.setattr(w1, "latest_grant", latest_grant)
    monkeypatch.setattr(organisations_api, "client_of_entity", client_of_entity)
    monkeypatch.setattr(organisations_api, "attest_client_of", attest_client_of)
    monkeypatch.setattr(cc, "get_ref", get_ref)
    monkeypatch.setattr(cc, "allowed_actions", allowed_actions)

    def session(_t: object) -> _Session:
        return _Session()

    monkeypatch.setattr(cc, "tenant_session", session)
    from abacus.modules.identity import api as identity_api

    monkeypatch.setattr(identity_api, "names_of", names_of)


async def _scope() -> Any:  # noqa: ANN401 -- the scope or None
    ctx = SimpleNamespace(tenant=None)
    return await write_scope(ctx, _entry(), _live(), engagement_id=uuid4(), entity_id=uuid4())


async def test_ac_no_write_copy_until_the_firm_holds_w1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, released=False)
    assert await _scope() is None
    _patch(monkeypatch, enabled=False)
    assert await _scope() is None
    _patch(monkeypatch, consent=None)
    assert await _scope() is None


async def test_ac_an_attest_client_reads_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, attest=True)
    found = await _scope()
    assert (found.state, found.consent, found.can_change) == ("read_only", None, False)


async def test_ac_offered_with_consent_v2_then_granted(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch)
    offered = await _scope()
    assert offered.state == "offered" and offered.can_change
    assert offered.consent.version == w1.CONSENT_COPY
    assert any("post" in line.lower() for line in offered.consent.will)
    assert "Change or delete existing transactions" in offered.consent.wont
    _patch(monkeypatch, grant=w1.LatestGrant("granted", SEP14_1022, TESS))
    granted = await _scope()
    assert (granted.state, granted.granted_by, granted.granted_at) == (
        "granted", "Tess Moreno", SEP14_1022,
    )  # fmt: skip
    _patch(monkeypatch, grant=w1.LatestGrant("revoked", SEP14_1022, TESS))
    assert (await _scope()).state == "offered"


async def test_ac_only_the_owner_may_change_it(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, may=())
    assert (await _scope()).can_change is False


async def test_ac_the_drawer_lists_posted_batches_and_the_closing_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = lc.LogRow(uuid4(), "2026-08-A", "2026-08", "posted", 6, 6, "48213", "48218", 0, 0,
                    SEP14_1022, uuid4())  # fmt: skip
    proposed = lc.LogRow(uuid4(), "2026-09-A", "2026-09", "proposed", 4, 0, None, None, 0, 0,
                         None, None)  # fmt: skip
    closing = lc.ClosingDate(date(2026, 8, 31), uuid4(), SEP14_1022.replace(minute=23))

    async def posting_facts(_t: object, _e: object) -> lc.PostingFacts:
        return lc.PostingFacts((proposed, row), 1, closing)

    monkeypatch.setattr(lc, "posting_facts", posting_facts)
    found = await writes(SimpleNamespace(tenant=None), uuid4())
    assert [(w.kind, w.batch_code, w.count, w.closing_date) for w in found] == [
        ("closing_date", None, None, date(2026, 8, 31)),
        ("posted_entries", "2026-08-A", 6, None),
    ]
