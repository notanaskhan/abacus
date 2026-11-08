# ac-test-author: ayushkbhatia
"""R-02-T07 (R-02-T10, TASK-6218; ADR-078): independent AC tests for C10's serving.

Written from the R-02-T10 row and R-02 §3.15 AC-38 to AC-41, not T07's tests. Row acceptance:
"Tests headed ac-test-author ayushkbhatia pass against T07 and fail if any page image or URL is
served without an audience grant." Covered: the link lives 60 seconds, set by the database and
bound to its tenant and person; the URL is the API's own route, never an object key or a presigned
URL; every audience the row names refuses the roles it must; an unwatermarked draft is never
served, page or file; a page view writes exactly one access row; a non-client, a non-person and an
ungranted person get 404.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.pdf_pages import PagePng
from abacus.modules.evidence import deliverable_serving as serving
from abacus.modules.identity.context import AuthContext
from abacus.modules.reporting import deliverable_reads as reads

MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations" / "versions"
CLIENT, ENGAGEMENT, WORK_ITEM, ROOM = uuid4(), uuid4(), uuid4(), uuid4()


def _ctx(*, kind: str = "human", client: bool = True) -> AuthContext:
    user = uuid4()
    return AuthContext(
        TenantContext(uuid4(), kind, str(user)),  # type: ignore[arg-type]
        user,
        uuid4(),
        None,
        datetime.now(UTC),
        client=client,
    )


def _reader(*, draft: bool = False, watermarked: bool = False) -> serving.ServableVersion:
    return serving.ServableVersion(
        version_id=uuid4(), version_no=1, evidence_version_id=uuid4(), is_draft=draft,
        watermarked=watermarked, page_count=3, title="Audit report", client_id=CLIENT,
        engagement_id=ENGAGEMENT, work_item_id=WORK_ITEM, tri=False, contact_id=uuid4(),
    )  # fmt: skip


# --- the link ----------------------------------------------------------------------------------


def _links_migration() -> str:
    [path] = [p for p in MIGRATIONS.glob("0712_*.py")]
    return path.read_text()


def test_the_link_lives_60_seconds_set_by_the_database() -> None:
    source = _links_migration()
    assert (
        "expires_at timestamptz NOT NULL DEFAULT statement_timestamp() + interval '60 seconds'"
        in source
    )
    assert "CHECK (expires_at <= issued_at + interval '60 seconds')" in source
    # The service never supplies either time: the database's clock decides.
    issue = serving._ISSUE.text  # pyright: ignore[reportPrivateUsage]
    insert = re.search(r"INSERT INTO deliverable_download_links\s*\((.*?)\)", issue, re.S)
    assert insert is not None
    assert "issued_at" not in insert.group(1) and "expires_at" not in insert.group(1)


def test_a_link_is_used_once_by_its_own_person_inside_its_life() -> None:
    use = serving._USE.text  # pyright: ignore[reportPrivateUsage]
    for clause in ("user_id = :user", "used_at IS NULL", "expires_at > clock_timestamp()"):
        assert clause in use


def test_the_link_is_bound_to_its_tenant() -> None:
    source = _links_migration()
    assert "tenant_table(op" in source or "FORCE ROW LEVEL SECURITY" in source
    assert "tenant_id" in serving._ISSUE.text  # pyright: ignore[reportPrivateUsage]


def test_the_url_is_the_api_s_route_never_an_object_key() -> None:
    link = uuid4()
    url = serving.FILE_ROUTE.format(link_id=link)
    assert url == f"/v1/portal/deliverable-files/{link}"
    assert not re.search(r"(s3://|X-Amz|amazonaws|Signature=)", url)


# --- the audience --------------------------------------------------------------------------------


@pytest.mark.parametrize("role", sorted(reads._NEVER))  # pyright: ignore[reportPrivateUsage]
def test_roles_that_never_read_a_deliverable_are_refused(role: str) -> None:
    audience = reads.Audience("client", CLIENT)
    assert not reads.covers(role, "client", CLIENT, CLIENT, None, None, audience, ENGAGEMENT)


def test_a_governance_room_is_tcwg_only_and_tcwg_reads_only_its_room() -> None:
    room = reads.Audience("governance_room", ROOM)
    assert reads.covers("tcwg", "governance_room", ROOM, None, None, None, room, ENGAGEMENT)
    assert not reads.covers("client_admin", "client", CLIENT, CLIENT, None, None, room, ENGAGEMENT)
    other = reads.Audience("governance_room", uuid4())
    assert not reads.covers("tcwg", "governance_room", ROOM, None, None, None, other, ENGAGEMENT)
    client = reads.Audience("client", CLIENT)
    assert not reads.covers(
        "tcwg", "governance_room", ROOM, CLIENT, None, None, client, ENGAGEMENT
    )


def test_another_client_or_engagement_is_out_of_scope() -> None:
    client = reads.Audience("client", CLIENT)
    assert not reads.covers(
        "client_admin", "client", uuid4(), uuid4(), None, None, client, ENGAGEMENT
    )
    engagement = reads.Audience("engagement", ENGAGEMENT)
    assert not reads.covers(
        "client_admin", "engagement", uuid4(), CLIENT, uuid4(), None, engagement, ENGAGEMENT
    )
    # A work-item grant reaches a work-item audience only, never its engagement's.
    assert not reads.covers(
        "client_admin",
        "work_item",
        WORK_ITEM,
        CLIENT,
        ENGAGEMENT,
        WORK_ITEM,
        engagement,
        ENGAGEMENT,
    )


@pytest.mark.parametrize(
    "ctx",
    [_ctx(client=False), _ctx(kind="agent"), _ctx(kind="system", client=False)],
    ids=["firm_person", "agent", "system"],
)
async def test_anyone_but_a_client_person_reads_404(ctx: AuthContext) -> None:
    with pytest.raises(NotFound):
        await reads.reader_version(ctx, uuid4(), 1)


# --- the draft watermark -------------------------------------------------------------------------


async def test_an_unwatermarked_draft_is_never_served() -> None:
    reader = _reader(draft=True, watermarked=False)
    ctx = _ctx()
    with pytest.raises(NotFound):
        await serving.deliverable_page(ctx, reader, 1)
    with pytest.raises(NotFound):
        await serving.issue_deliverable_download(ctx, reader)
    with pytest.raises(NotFound):
        await serving.open_deliverable_download(ctx, uuid4(), reader)


# --- one access row per request ------------------------------------------------------------------


async def test_a_page_view_writes_one_access_row(monkeypatch: pytest.MonkeyPatch) -> None:
    rows: list[tuple[str, int]] = []

    async def stored(_ctx: AuthContext, _version: UUID) -> tuple[bytes, str]:
        return b"%PDF-", "application/pdf"

    def render(_content: bytes, page: int) -> PagePng:
        return PagePng(page, 3, png=b"png")

    async def record(
        _tenant: object, kind: str, subjects: list[Any], **_: object
    ) -> None:  # Any: test double
        rows.append((kind, len(subjects)))

    monkeypatch.setattr(serving, "_bytes", stored)
    monkeypatch.setattr(serving, "render_page_isolated", render)
    monkeypatch.setattr(serving, "record_reads", record)
    for watermarked_draft in (False, True):
        reader = _reader(draft=watermarked_draft, watermarked=watermarked_draft)
        page = await serving.deliverable_page(_ctx(), reader, 2)
        assert page.media_type == "image/png"
    assert rows == [(serving.PAGE_VIEW, 1), (serving.PAGE_VIEW, 1)]


async def test_a_page_outside_the_document_is_404_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows: list[str] = []

    async def record(_tenant: object, kind: str, *_: object, **__: object) -> None:
        rows.append(kind)

    monkeypatch.setattr(serving, "record_reads", record)
    with pytest.raises(NotFound):
        await serving.deliverable_page(_ctx(), _reader(), 4)
    assert rows == []
