"""N-02-T36 (TASK-2528; DEC-1573) on the loaded Brightwater Hale tenant: "make seed-demo
reproduces the SIG-01 counts at E0." The `signatures` slice loads into its own database, then
SIG-01's summary is read as Grace Holloway (client service on the clients' engagements, DEC-20)
at Mon Sep 14, 2026, 9:24 AM CT:
2 to send, 17 out, 6 completed in 30 days, 1 expired; by type 10 e-file, 4 letters, 2 rep, 1
consent. Irene Kowal's identity check is locked after three failures; the ERSD disclosure v1 is
the firm's database content. Figures typed from the SIG-01 handoff."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import AuthContext
from abacus.modules.signatures import hub
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.people import FIRM_ROLES, slug_of
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
T0 = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # 9:24 AM Central
GRACE = uuid.UUID(stable_id(f"user:{slug_of('Grace Holloway')}"))


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_ac_seed_demo_reproduces_the_sig01_counts_at_e0(
    own_db: Database, migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    await loader.load(own_db.superuser_dsn, "E0", slices=("signatures",), wait=False)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'signatures.envelopes', 'true', 'test-seed', 'N-02-T36 E0') "
        "ON CONFLICT DO NOTHING",
        TENANT,
    )
    # DEC-20: Grace's need-to-know is client_service on the engagements.
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "SELECT tenant_id, id, $2::uuid, 'client_service' FROM engagements "
        "WHERE tenant_id = $1 ON CONFLICT DO NOTHING",
        TENANT,
        GRACE,
    )
    grace = AuthContext(
        tenant=TenantContext(TENANT, "human", str(GRACE)),
        user_id=GRACE,
        membership_id=uuid.uuid4(),
        firm_role=FIRM_ROLES["GH"],
        mfa_at=T0 - timedelta(minutes=1),
    )
    with clock.frozen(T0):
        made = await hub.summary(grace)
    assert (made.to_send, made.out, made.completed, made.expired) == (2, 17, 6, 1)
    by_type = dict(made.by_type)
    assert (by_type.get("efile"), by_type.get("engagement_letter")) == (10, 4)
    assert (by_type.get("rep_letter"), by_type.get("consent_7216")) == (2, 1)

    irene = await seed.rows(
        "SELECT s.status, s.kba_failures FROM envelope_signers s JOIN envelopes e "
        'ON e.id = s.envelope_id WHERE e.tenant_id = $1 AND e.number = 2 AND s."order" = 2',
        TENANT,
    )
    assert [(r["status"], r["kba_failures"]) for r in irene] == [("verification_failed", 3)]
    disclosures = await seed.rows(
        "SELECT version_no FROM esign_disclosures WHERE tenant_id = $1", TENANT
    )
    assert [d["version_no"] for d in disclosures] == [1]
    # Loading again changes nothing (stable ids, ON CONFLICT): the counts stay.
    await loader.load(own_db.superuser_dsn, "E0", slices=("signatures",), wait=False)
    with clock.frozen(T0):
        again = await hub.summary(grace)
    assert (again.to_send, again.out) == (2, 17)
