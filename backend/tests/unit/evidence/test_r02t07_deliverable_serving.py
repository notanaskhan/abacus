"""R-02-T07 (TASK-6107; R-02 §3.15 AC-38, AC-39; ADR-104): serving refusals that need no database.
A draft that is not a C11 draft-mode render is never served, page or file; a page outside the
version is 404; the download URL is the API's file route with a link id, never an object key or a
presigned URL."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.evidence import deliverable_serving as serving
from abacus.modules.identity.api import AuthContext

pytestmark = pytest.mark.asyncio


def _version(*, is_draft: bool, watermarked: bool, pages: int = 14) -> serving.ServableVersion:
    return serving.ServableVersion(
        version_id=uuid4(),
        version_no=3,
        evidence_version_id=uuid4(),
        is_draft=is_draft,
        watermarked=watermarked,
        page_count=pages,
        title="Financial statements and supplemental schedules",
        client_id=uuid4(),
        engagement_id=uuid4(),
        work_item_id=uuid4(),
        tri=False,
        contact_id=uuid4(),
    )


def _ctx() -> AuthContext:
    return AuthContext(
        TenantContext(uuid4(), "human", str(uuid4())),
        uuid4(),
        uuid4(),
        None,
        datetime(2026, 10, 8, tzinfo=UTC),
        client=True,
    )


async def test_ac38_an_unwatermarked_draft_page_is_never_served() -> None:
    with pytest.raises(NotFound):
        await serving.deliverable_page(_ctx(), _version(is_draft=True, watermarked=False), 2)


async def test_ac38_an_unwatermarked_draft_file_is_never_issued() -> None:
    with pytest.raises(NotFound):
        await serving.issue_deliverable_download(
            _ctx(), _version(is_draft=True, watermarked=False)
        )


async def test_ac38_and_never_opened() -> None:
    with pytest.raises(NotFound):
        await serving.open_deliverable_download(
            _ctx(), uuid4(), _version(is_draft=True, watermarked=False)
        )


@pytest.mark.parametrize("page", [0, -1, 15])
async def test_a_page_outside_the_version_is_404(page: int) -> None:
    with pytest.raises(NotFound):
        await serving.deliverable_page(_ctx(), _version(is_draft=False, watermarked=False), page)


def test_ac39_the_url_is_the_api_s_file_route_never_an_object_key() -> None:
    link = uuid4()
    url = serving.FILE_ROUTE.format(link_id=link)
    assert url == f"/v1/portal/deliverable-files/{link}"
    assert "s3" not in url and "X-Amz" not in url and "?" not in url


def test_ac40_page_views_and_downloads_are_access_kinds() -> None:
    from abacus.kernel.uow.access import _KINDS  # pyright: ignore[reportPrivateUsage]

    assert {serving.PAGE_VIEW, serving.DOWNLOAD} <= set(_KINDS)
