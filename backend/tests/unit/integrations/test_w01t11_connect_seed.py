"""W-01-T11 (SPEC-659 AC-1 to AC-3, AC-6, AC-23; DF-34): golden tests of the Brightwater Hale
`connect` slice against the reviewed catalogue and the catalogue service.

The slice's installs, read through `tile_of` over the document's rows with the fakes on (the
synthetic tenant), give WB-10 the design's counts: 53 = 9 + 38 + 6 at E0 and 55 = 9 + 40 + 6 at
E2 (WB-10 a, h), with Felix Andersen's nine connected tiles (WB-10 c) and the scenario fixture's
names (the web fixtures read the same content: fixture mode and the seed show the same data).
Hannah Leclerc reads Box connected as her own and the firm tiles managed by Felix (WB-10 d);
Workstream reads its prerequisite reason (WB-10 a); CCH is a file bridge (AC-23).
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from abacus.kernel import config
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.integrations.catalog_import import CatalogDocumentV2
from abacus.modules.integrations.connect_catalog import (
    Install,
    Tile,
    WorkbenchRow,
    published,
    tile_of,
)
from abacus_tools import integration_catalog as ops
from abacus_tools.synthetic.scenarios.brightwater_hale import connect_catalog as scenario
from abacus_tools.synthetic.scenarios.brightwater_hale import connect_slice as seed

DOCUMENT = Path(ops.__file__).resolve().parent / "catalogue" / "connect_v2.yaml"
FELIX = uuid.UUID(int=1)
HANNAH = uuid.UUID(int=2)


@pytest.fixture(autouse=True)
def fakes_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "test")
    monkeypatch.setenv("ABACUS_INTEGRATIONS_FAKE_ADAPTERS", "true")
    config.settings.cache_clear()
    yield
    config.settings.cache_clear()


def _rows() -> list[WorkbenchRow]:
    doc = CatalogDocumentV2.model_validate(yaml.safe_load(DOCUMENT.read_text(encoding="utf-8")))
    return [
        WorkbenchRow(
            key=r.key,
            name=r.name,
            categories=tuple(r.categories),
            ownership_mode=r.ownership_mode,
            connector_provider=r.connector_provider,
            adapter_key=r.adapter_key,
            listing_status=r.listing_status,
            consent_copy=None,
            consent_version=r.consent_version,
            read_scopes=tuple((s.code, s.label) for s in r.scopes.read),
            icon=r.icon,
            tone=r.tone,
            sort_order=r.sort_order,
            description=r.description or "",
            auth_line=r.auth_line or "",
            published_at=r.published_at,
            prerequisite=None if r.prerequisite is None else r.prerequisite.model_dump(),
            revision=1,
        )
        for r in doc.rows
        if "workbench" in r.surfaces
    ]


def _installs(person: str) -> tuple[dict[str, Install], dict[str, Install]]:
    firm: dict[str, Install] = {}
    mine: dict[str, Install] = {}
    for i in seed.INSTALLS:
        install = Install(uuid.uuid4(), "connected", i.mode, FELIX, i.granted_scopes, 1)
        if i.scope == "firm":
            firm[i.key] = install
        elif i.person == person:
            mine[i.key] = install
    return firm, mine


def _tiles(person: str, role: str | None, at: datetime) -> list[Tile]:
    firm, mine = _installs(person)
    ctx = AuthContext(TenantContext(uuid.uuid4(), "human", "u"), FELIX, uuid.uuid4(), role, at)  # type: ignore[arg-type] -- a matrix role code
    return [
        tile_of(
            r,
            ctx=ctx,
            synthetic=True,
            firm=firm,
            mine=mine,
            names={FELIX: seed.FELIX},
            manager=seed.FELIX,
        )
        for r in published(_rows(), at)
    ]


def _counts(tiles: list[Tile]) -> dict[str, int]:
    buckets = Counter(t.bucket for t in tiles)
    return {
        "all": len(tiles),
        "connected": buckets["connected"],
        "available": buckets["available"],
        "coming_soon": buckets["coming_soon"],
    }


def test_ac1_e0_reads_53_9_38_6_for_felix() -> None:
    assert _counts(_tiles(seed.FELIX, "security_admin", scenario.E0)) == scenario.status_counts(
        scenario.E0
    )


def test_ac3_e2_reads_55_9_40_6() -> None:
    assert _counts(_tiles(seed.FELIX, "security_admin", scenario.E2)) == scenario.status_counts(
        scenario.E2
    )


def test_wb10_c_felixs_nine_connected_tiles_are_the_fixtures() -> None:
    tiles = _tiles(seed.FELIX, "security_admin", scenario.E0)
    connected = [t.row.name for t in tiles if t.bucket == "connected"]
    assert sorted(connected) == sorted(scenario.connected_names(scenario.E0))


def test_wb10_d_hannah_reads_box_as_her_own_and_firm_tiles_managed_by_felix() -> None:
    tiles = {t.row.key: t for t in _tiles(seed.HANNAH, None, scenario.E0)}
    assert tiles["box"].viewer_status == "connected"
    assert tiles["m365"].status == "available"  # Felix's own, not hers
    assert tiles["ultratax"].blocked_reason == "Felix Andersen manages firm connections."


def test_wb10_a_workstream_reads_its_prerequisite_reason_and_cch_is_a_file_bridge() -> None:
    tiles = {t.row.key: t for t in _tiles(seed.FELIX, "security_admin", scenario.E0)}
    assert tiles["workstream"].blocked_reason is not None
    assert tiles["workstream"].blocked_reason.startswith("Uses the CCH Axcess firm account")
    assert tiles["cch"].kind == "file_bridge"
    assert tiles["quickbooks_online"].kind == "client_authorised"


def test_df34_cch_was_connected_jan_14_9_12_by_felix() -> None:
    cch = next(i for i in seed.INSTALLS if i.key == "cch")
    assert cch.connected_at.isoformat() == "2026-01-14T09:12:00-06:00"
    assert len(seed.CCH_TIMELINE) + 2 == 5  # the connect, three imports, the Sep 14 import
