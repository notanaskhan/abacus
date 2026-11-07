"""P-11-T30 (TASK-6010; ADR-078): the viewer refuses OCR pages to readers who may not see them.

The row's open properties: "offshore refusal until masked" and "walls and client refusal on fields
and tables". An offshore reader (`may_read_unmasked` false) gets no page image at all, whatever OCR
or the scan found: 403 before anything is read, and reads the masked text instead. A walled or
other-firm version is 404 on every read (page, text, regions), before any page or word is read.
Written outside the implementing session (ADR-078).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.evidence import viewer
from abacus.modules.identity.api import AuthContext, Forbidden

CTX = cast(AuthContext, SimpleNamespace(tenant=None, tenant_id=uuid4(), user_id=uuid4()))
VERSION = SimpleNamespace(id=uuid4())
reads: list[str] = []


@pytest.fixture(autouse=True)
def _record(monkeypatch: pytest.MonkeyPatch) -> None:
    reads.clear()

    async def masked_page(_ctx: object, _version: object, page_no: int) -> bytes:
        reads.append(f"page:{page_no}")
        return b"png"

    def no_session(_tenant: object) -> object:
        reads.append("session")
        raise AssertionError("nothing is read for a refused reader")

    monkeypatch.setattr(viewer, "_masked_page", masked_page)
    monkeypatch.setattr(viewer, "tenant_session", no_session)


def _visible(monkeypatch: pytest.MonkeyPatch, *, walled: bool) -> None:
    async def visible(_ctx: object, _version_id: object) -> object:
        if walled:
            raise NotFound("evidence_version")
        return VERSION

    monkeypatch.setattr(viewer, "visible_version", visible)


def _offshore(monkeypatch: pytest.MonkeyPatch, offshore: bool) -> None:
    async def may_read_unmasked(_ctx: object) -> bool:
        return not offshore

    monkeypatch.setattr(viewer, "may_read_unmasked", may_read_unmasked)


async def test_an_offshore_reader_gets_no_page_image(monkeypatch: pytest.MonkeyPatch) -> None:
    _visible(monkeypatch, walled=False)
    _offshore(monkeypatch, True)
    with pytest.raises(Forbidden):
        await viewer.viewer_page(CTX, uuid4(), 1)
    assert reads == []


async def test_an_onshore_reader_gets_the_masked_page(monkeypatch: pytest.MonkeyPatch) -> None:
    _visible(monkeypatch, walled=False)
    _offshore(monkeypatch, False)
    assert await viewer.viewer_page(CTX, uuid4(), 2) == b"png"
    assert reads == ["page:2"]


@pytest.mark.parametrize("offshore", [False, True])
async def test_a_walled_version_is_404_on_every_read(
    monkeypatch: pytest.MonkeyPatch, offshore: bool
) -> None:
    _visible(monkeypatch, walled=True)
    _offshore(monkeypatch, offshore)
    with pytest.raises(NotFound):
        await viewer.viewer_page(CTX, uuid4(), 1)
    with pytest.raises(NotFound):
        await viewer.viewer_text(CTX, uuid4())
    with pytest.raises(NotFound):
        await viewer.viewer_regions(CTX, uuid4(), None)
    assert reads == []


async def test_a_client_principal_is_refused_before_anything_is_read() -> None:
    client = cast(AuthContext, SimpleNamespace(tenant=None, tenant_id=uuid4(), client=True))
    with pytest.raises(Forbidden):
        await viewer.visible_version(client, uuid4())
