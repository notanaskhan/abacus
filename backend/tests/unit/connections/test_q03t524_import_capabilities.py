# ac-test-author: ayushkbhatia
"""Q-03-T524: back-fill of TASK-053, SPEC-028 AC-7, black-box from the spec.

AC-7: the import connector reports its capabilities (no OAuth, no change feed, no attachments);
`changes_since` and `fetch_attachment` raise `NotSupported`. The conformance half of AC-7 is
`test_import_conformance.py` (TASK-052's suite, run against the same connector).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.modules.connections.connector import NotSupported
from abacus.modules.connections.connectors.import_file import ImportConnector


def _connector() -> ImportConnector:
    return ImportConnector(uuid.uuid4(), uuid.uuid4())


def test_ac7_the_import_connector_reports_no_oauth_no_change_feed_no_attachments() -> None:
    caps = _connector().capabilities()
    assert caps.oauth is False
    assert caps.incremental is False
    assert caps.attachments is False
    assert caps.datasets == frozenset({"trial_balance"})


async def test_ac7_changes_since_raises_not_supported() -> None:
    with pytest.raises(NotSupported):
        await _connector().changes_since(datetime(2026, 9, 14, tzinfo=UTC))


async def test_ac7_fetch_attachment_raises_not_supported() -> None:
    with pytest.raises(NotSupported):
        await _connector().fetch_attachment("anything")


async def test_ac7_no_sign_in_flow_exists() -> None:
    connector = _connector()
    with pytest.raises(NotSupported):
        await connector.authorise_url("state", "https://example.invalid/cb")
    with pytest.raises(NotSupported):
        await connector.exchange_code("code", "https://example.invalid/cb")
