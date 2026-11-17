"""W-01-T07 rest (TASK-8446; DEC-5433; SPEC-659 AC-4, OQ-9; ADR-157) against Postgres.

`integration_pause` (0948) is keyed by the catalogue key, per firm or platform-wide. While it is
on, an installed integration reads "Paused" with Enable and Reconnect hidden, an uninstalled one is
not `available` (AC-4), a connect start refuses 409 `integration_paused`, and another firm (for a
firm row) or another integration is untouched. The keyed CHECK holds for both keyed controls.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from abacus.kernel.controls import forget_controls
from abacus.modules.integrations import connect_service as svc
from abacus.modules.integrations.connect_catalog import Catalogue, catalogue
from abacus.modules.integrations.kill_switch import IntegrationPaused

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_w01t08_firm_app_suspend import (
    _world,  # pyright: ignore[reportPrivateUsage] -- the same synthetic firm
)
from .test_w01t08_firm_app_suspend import (
    db as db,  # the probe catalogue import (a fixture)
)
from .test_w01t08_firm_app_suspend import (
    fakes_on as fakes_on,
)

pytestmark = pytest.mark.usefixtures("fakes_on")


@pytest.fixture(autouse=True)
def fresh_controls() -> object:
    forget_controls()
    yield None
    forget_controls()


async def _pause(seed: Seeder, key: str, tenant: uuid.UUID | None, *, on: bool = True) -> None:
    await seed.run(
        "SELECT set_platform_control('integration_pause', $1, $2, $3, $4, 'probe incident', "
        "'probe-op', NULL)",
        "firm" if tenant else "platform",
        tenant,
        key,
        on,
    )
    forget_controls()


def _tile(tiles: Catalogue, key: str) -> tuple[str, tuple[str, ...]]:
    found = next(t for t in tiles.tiles if t.row.key == key)
    return found.status, found.allowed_actions


async def test_ac4_a_paused_install_reads_paused_and_cannot_reconnect(
    db: MigratedDatabase,
) -> None:
    seed, felix, _ = await _world(db)
    await svc.start_firm(felix, "probeapp")
    before = _tile(await catalogue(felix), "probeapp")
    assert before[0] == "connected" and "integration.connect_firm" in before[1]

    await _pause(seed, "probeapp", None)  # platform-wide: switched off again below
    try:
        status, actions = _tile(await catalogue(felix), "probeapp")
        assert status == "paused"
        assert "integration.connect_firm" not in actions
        assert "integration.disconnect_firm" in actions  # taking access away stays
        with pytest.raises(IntegrationPaused):
            await svc.start_firm(felix, "probeapp")
    finally:
        await _pause(seed, "probeapp", None, on=False)
    assert _tile(await catalogue(felix), "probeapp")[0] == "connected"


async def test_ac4_a_firm_pause_is_that_firms_and_that_integrations(db: MigratedDatabase) -> None:
    seed, felix, _ = await _world(db)
    _, other, _ = await _world(db)
    await _pause(seed, "probeapp", felix.tenant_id)

    assert _tile(await catalogue(felix), "probeapp")[0] == "coming_soon"  # not installed
    with pytest.raises(IntegrationPaused):
        await svc.start_firm(felix, "probeapp")
    assert _tile(await catalogue(other), "probeapp")[0] == "available"
    started = await svc.start_firm(other, "probeapp")
    assert started.status == "connected"


async def test_the_keyed_check_holds_for_both_keyed_controls(db: MigratedDatabase) -> None:
    seed = Seeder(db.superuser_dsn)
    for control, route in (("integration_pause", None), ("ai_pause", "probeapp")):
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "SELECT set_platform_control($1, 'platform', NULL, $2, true, 'probe', "
                "'probe-op', NULL)",
                control,
                route,
            )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "SELECT set_platform_control('model_route_block', 'platform', NULL, NULL, true, "
            "'probe', 'probe-op', NULL)"
        )
