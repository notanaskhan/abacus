"""Q-02-T48: the real-data rehearsal as a system test (Q-02 §10 DoD 5; DEC-958).

It runs only where the rehearsal tenant exists: on staging, inside the VPC, with the tenant's ids
in `ABACUS_REHEARSAL_TENANT`, `_ADMIN`, `_PARTNER`, `_ENGAGEMENT` and `_TAX_ENGAGEMENT` (the ops
task passes them; `rehearsal-nightly.yml` starts it). Everywhere else it is skipped. The walk is
`abacus_tools.rehearsal.walk`, shared with the ops command, so the nightly run and this test check
the same steps: every refusal reason but `terms`, opt-in, shadow, exclusion, the live-stage guard,
access events, the audit chain, INV-1 and INV-5."""

from __future__ import annotations

import os
from uuid import UUID

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus_tools.rehearsal import Rehearsal, walk

_KEYS = ("TENANT", "ADMIN", "PARTNER", "ENGAGEMENT", "TAX_ENGAGEMENT")
_IDS = {k: os.environ.get(f"ABACUS_REHEARSAL_{k}") for k in _KEYS}

pytestmark = pytest.mark.skipif(
    any(v is None for v in _IDS.values()) or os.environ.get("ABACUS_ENVIRONMENT") != "staging",
    reason="the rehearsal runs on staging only, with the rehearsal tenant's ids (#617)",
)


async def test_the_rehearsal_walks_opt_in_shadow_live_guard_and_every_refusal() -> None:
    url = settings().database_url
    assert url is not None
    configure_engine(url.get_secret_value())
    try:
        found = await walk(Rehearsal(*(UUID(str(_IDS[k])) for k in _KEYS)))
    finally:
        await dispose_engine()
    assert found.failed == 0, "\n".join(found.lines)
