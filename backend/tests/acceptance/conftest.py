"""Q-01 acceptance tests (ADR-078): a clean process-wide state for every test.

The suites here drive the adapters through their public names and the HTTP edge through
`create_app()`. No test talks to AWS; the only network they open is loopback.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import reset_key_service
from abacus.kernel.scanning import configure_scanner
from abacus.kernel.temporal import configure_temporal_client
from abacus.modules.communications.transport import configure_transport


def _reset() -> None:
    settings.cache_clear()
    reset_key_service()
    configure_scanner(None)
    configure_transport(None)
    configure_temporal_client(None)


@pytest.fixture(autouse=True)
def clean_process(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No `ABACUS_*` variable from the developer's shell leaks in, and no installed adapter or
    cached settings leak out."""
    for name in list(os.environ):
        if name.startswith("ABACUS_"):
            monkeypatch.delenv(name)
    _reset()
    yield
    _reset()
