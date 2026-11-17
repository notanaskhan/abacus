"""A-08-T22 rest (S48): the SSARS rail's FS row reads the statements package's own state."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.reporting import statements as st

T = TenantContext(uuid.uuid4(), "system", "test")


def _version(out_of_date: bool) -> st.VersionView:
    return st.VersionView({}, [], out_of_date, None)


@pytest.mark.parametrize(
    ("view", "state"),
    [
        (st.DocumentView(None, None), "not_started"),
        (st.DocumentView({"status": "draft"}, None), "not_started"),
        (st.DocumentView({"status": "draft"}, _version(False)), "draft"),
        (st.DocumentView({"status": "draft"}, _version(True)), "out_of_date"),
        (st.DocumentView({"status": "published"}, _version(False)), "published"),
        (st.DocumentView({"status": "published"}, _version(True)), "out_of_date"),
    ],
)
async def test_the_package_reads_as_one_status_word(
    monkeypatch: pytest.MonkeyPatch, view: st.DocumentView, state: str
) -> None:
    async def found(*_: object) -> st.DocumentView:
        return view

    monkeypatch.setattr(st, "current_of", found)
    assert await st.package_state(T, uuid.uuid4()) == state
