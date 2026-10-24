"""G-01-T06 against Postgres (G-01 AC3.1, AC5.1; ADM-01a, ADM-02a, ADM-02b): E0 loaded with the
`people` slice reads live on ADM-02's services with counts that foot to 46: the bands
7 + 7 + 11 + 14 + 5 + 2 in the screen's order, the tally "46 of 46", 7 partners · 37
professionals · 2 operations, five seasonal ending Oct 31, templates 7 + 4 + 6 + 8 + 8 + 11 + 1 +
1, teams 16 + 21 + 7 + 2, Felix Andersen as the security admin and Grace Holloway the one firm
admin. A second load writes nothing. The figures are typed from ADM-02 and G-01 section 5.3.

The load gets its own database: the session's `migrated_db` holds the loader test's E0."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

import abacus.modules.organisations.api  # registers member teams and the office list
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity import people
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.people import StaffFilters
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.organisations.api
pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


def _grace() -> AuthContext:
    user = UUID(stable_id("user:grace-holloway"))
    return AuthContext(
        tenant=TenantContext(TENANT, "human", str(user)),
        user_id=user,
        membership_id=uuid4(),
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def test_e0_with_the_people_slice_foots_to_46(
    own_db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    await dispose_engine()  # the identity engine reads the new URL when next asked
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    events = build("E0", slices=("audit_core", "people")).events
    first = await loader.load(own_db.superuser_dsn, "E0", slices=("people",), wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)

    grace = _grace()
    page = await people.staff_page(grace, StaffFilters(limit=200))
    assert page.total == 46
    assert page.counts == {
        "partners": 7,
        "managers": 7,
        "seniors": 11,
        "staff": 14,
        "seasonal": 5,
        "operations": 2,
    }
    names = [r.display_name for r in page.items]
    assert names[:3] == ["Margaret Okonkwo", "Daniel Reyes", "Priya Raman"]
    assert names[39:46] == [
        "Lena Park",
        "Maya Adler",
        "Paige Sutton",
        "Noel Kirby",
        "Remy Vidal",
        "Grace Holloway",
        "Felix Andersen",
    ]
    t = page.tallies
    assert (t.seats_used, t.seats_total, t.seats_pending) == (46, 46, 0)
    assert (t.partners, t.professionals, t.operations) == (7, 37, 2)
    assert (t.seasonal, t.seasonal_access_ends_on) == (5, date(2026, 10, 31))
    teams = await seed.rows(
        "SELECT t.name, count(*) AS n FROM team_rosters r JOIN teams t ON t.id = r.team_id "
        "WHERE r.tenant_id = $1 GROUP BY t.name",
        TENANT,
    )
    assert {r["name"]: r["n"] for r in teams} == {
        "Audit & assurance": 16,
        "Tax": 21,
        "Client accounting": 7,
        "Firm operations": 2,
    }
    roles = await seed.rows(
        "SELECT firm_role, count(*) AS n FROM memberships WHERE tenant_id = $1 "
        "AND firm_role IS NOT NULL GROUP BY firm_role",
        TENANT,
    )
    assert {r["firm_role"]: r["n"] for r in roles} == {
        "firm_admin": 1,
        "security_admin": 1,
        "practice_leader": 1,
        "quality_partner": 1,
    }
    lena = next(r for r in page.items if r.display_name == "Lena Park")
    assert (lena.role_template, lena.level, lena.service_lines) == (
        "tax_preparer",
        "seasonal",
        ["tax"],
    )

    templates = await people.role_templates(grace)
    assert Counter({t.key: t.member_count for t in templates.templates}) == Counter(
        partner=7,
        manager=4,
        tax_reviewer=6,
        senior=8,
        staff=8,
        tax_preparer=11,
        firm_admin=1,
        it_security=1,
    )

    again = await loader.load(own_db.superuser_dsn, "E0", slices=("people",), wait=False)
    assert again.replayed == 0
    await dispose_engine()
    settings.cache_clear()
