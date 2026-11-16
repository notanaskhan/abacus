"""WB-11's live drawer projection (S47, TASK-8338) against Postgres: `connect_detail.drawer` reads
WB-10's tile and the install behind it; an unlisted key is 404. Uses W-01-T08's catalogue probe.
"""

from __future__ import annotations

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.integrations import connect_detail
from abacus.modules.integrations import connect_service as svc

from .conftest import MigratedDatabase
from .test_w01t08_connect import (
    _firm,  # pyright: ignore[reportPrivateUsage] -- W-01-T08's probe firm
    _person,  # pyright: ignore[reportPrivateUsage] -- W-01-T08's probe person
    _state,  # pyright: ignore[reportPrivateUsage] -- W-01-T08's OAuth state reader
)
from .test_w01t08_connect import db as db
from .test_w01t08_connect import fakes_on as fakes_on

pytestmark = pytest.mark.usefixtures("fakes_on")


async def test_a_connected_firm_token_reads_its_install(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    felix = await _person(db, tenant, "security_admin")
    started = await svc.start_firm(felix, "karbon")
    await svc.complete(felix, _state(started.authorise_url), "c")
    found = await connect_detail.drawer(felix, "karbon")
    assert found.tile.status == "connected"
    assert (found.card.mode, found.card.auth_mode_label) == ("token", "Firm connection")
    assert found.card.connected_by == "Probe person"
    assert found.card.connected_at is not None
    # The fake grants only `fake.read`, so the catalogue's `files.read` reads off for the firm.
    assert [(r.label, r.state) for r in found.reads] == [("Files", "off_for_firm")]
    assert found.never == ()  # a firm app's never lines are catalogue content not yet carried
    assert found.version >= 1
    assert "integration.disconnect_firm" in found.tile.allowed_actions


async def test_a_personal_app_reads_its_consent_never_lines(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    hannah = await _person(db, tenant, None)
    found = await connect_detail.drawer(hannah, "box")
    assert found.card.mode == "personal"
    assert found.card.connected_by is None
    assert [(r.label, r.state) for r in found.never] == [("Delete or share files", "never")]
    assert found.managed_by is None
    assert found.events == ()


async def test_a_key_wb10_does_not_list_is_404(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    felix = await _person(db, tenant, "security_admin")
    with pytest.raises(NotFound):
        await connect_detail.drawer(felix, "nope")
