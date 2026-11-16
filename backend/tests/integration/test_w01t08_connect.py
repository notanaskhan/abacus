"""W-01-T08 (SPEC-659 AC-10 to AC-16, AC-24 to AC-26) against Postgres with the Connect fakes on
a synthetic firm (W-01-T09).

A state is single-use, ten minutes, the caller's: a replayed, expired or other person's state is
`invalid_state` and a declined grant `connect_declined` (AC-12); a completed connect seals the
token and writes an event and an audit event naming the person; a firm app is connected at once
(AC-16); a missing prerequisite scope is refused (AC-15); the firm disconnect wants the typed name
(AC-24) and the version it saw, then erases the secret; a personal disconnect is the caller's own
only (AC-26); a deactivated person's personal installs end (AC-13); a real firm has no fakes.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from urllib.parse import parse_qs, urlparse

import pytest

from abacus.kernel import config
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.integrations import connect_service as svc
from abacus.modules.integrations.api import CatalogDocumentV2
from abacus.modules.integrations.connect_errors import (
    ConfirmNameMismatch,
    ConnectDeclined,
    IntegrationNotAvailable,
    InvalidState,
    PrerequisiteScopeMissing,
    StaleVersion,
)
from abacus_tools import integration_catalog as ops

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.usefixtures("fakes_on")

CONSENT = {
    "title": "Connect Box",
    "will": ["See your Box files you choose"],
    "wont": ["Delete or share files"],
    "authorization": "I'm connecting my own account.",
    "continue_label": "Continue",
}


def _row(key: str, **over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "key": key,
        "name": key.title(),
        "categories": ["docs"],
        "ownership_mode": "firm",
        "surfaces": ["workbench"],
        "adapter_key": key,
        "listing_status": "available",
        "scopes": {"read": [{"code": "files.read", "label": "Files"}]},
        "icon": "folder",
        "tone": "clay",
        "sort_order": 20,
        "description": "Files and folders.",
        "auth_line": "Firm connection",
        "published_at": "2026-01-01T00:00:00-06:00",
    }
    row.update(over)
    return row


DOC = CatalogDocumentV2.model_validate(
    {
        "version": 2,
        "rows": [
            _row("karbon", categories=["practice"]),
            _row(
                "box",
                ownership_mode="personal",
                auth_line="Personal",
                consent_copy=CONSENT,
                consent_version=1,
            ),
            _row(
                "drata",
                categories=["grc"],
                ownership_mode="client_authorised",
                connector_provider="drata_feed",
                auth_line="Firm app · client-authorized",
            ),
            _row(
                "workstream",
                categories=["practice"],
                prerequisite={
                    "key": "cch",
                    "scope": "workstream",
                    "reason": "Uses the CCH Axcess firm account, which does not yet grant it.",
                },
            ),
        ],
    }
)


@pytest.fixture
def fakes_on(monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setenv("ABACUS_INTEGRATIONS_FAKE_ADAPTERS", "true")
    config.settings.cache_clear()
    yield None
    config.settings.cache_clear()


@pytest.fixture
async def db(migrated_db: MigratedDatabase) -> AsyncIterator[MigratedDatabase]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    await ops.import_v2(
        migrated_db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1),
        DOC,
        "b" * 64,
        "probe-op",
        "W-01-T08 probe",
        environment="test",
        dry_run=False,
    )
    yield migrated_db
    await dispose_engine()


async def _firm(db: MigratedDatabase, *, synthetic: bool = True) -> uuid.UUID:
    seed = Seeder(db.superuser_dsn)
    tenant_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Probe', $2)",
        tenant_id,
        synthetic,
    )
    return tenant_id


async def _person(db: MigratedDatabase, tenant_id: uuid.UUID, role: str | None) -> AuthContext:
    seed = Seeder(db.superuser_dsn)
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://identity.abacus.local', $1, $2, 'Probe person') RETURNING id",
            subject,
            f"{subject}@example.test",
        ),
    )
    membership = await seed.value(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, $3, 'active') RETURNING id",
        tenant_id,
        user_id,
        role,
    )
    tenant = TenantContext(tenant_id, "human", str(user_id))
    return AuthContext(tenant, user_id, cast(uuid.UUID, membership), role, datetime.now(UTC))  # type: ignore[arg-type] -- a matrix role code


def _state(url: str | None) -> str:
    assert url is not None
    return parse_qs(urlparse(url).query)["state"][0]


async def test_ac10_ac11_a_personal_connect_completes_once_and_names_the_person(
    db: MigratedDatabase,
) -> None:
    tenant = await _firm(db)
    hannah = await _person(db, tenant, None)
    started = await svc.start_personal(hannah, "box")
    assert started.status == "connecting"
    state = _state(started.authorise_url)
    assert await svc.complete(hannah, state, "code-1") == "box"
    seed = Seeder(db.superuser_dsn)
    row = await seed.rows(
        "SELECT u.status, u.consent_version, s.sealed IS NOT NULL AS sealed "
        "FROM user_integrations u JOIN integration_secrets s ON s.user_integration_id = u.id "
        "WHERE u.tenant_id = $1",
        tenant,
    )
    assert [(r["status"], r["consent_version"], r["sealed"]) for r in row] == [
        ("connected", 1, True)
    ]
    stored = await seed.value(
        "SELECT count(*) FROM integration_oauth_states WHERE tenant_id = $1 AND state_sha256 = $2",
        tenant,
        svc.state_hash(state),
    )
    assert stored == 1  # only the hash is stored
    events = await seed.rows(
        "SELECT kind, actor_user_id FROM integration_events WHERE tenant_id = $1 ORDER BY at",
        tenant,
    )
    assert [(e["kind"], e["actor_user_id"]) for e in events] == [
        ("connect_started", hannah.user_id),
        ("connected", hannah.user_id),
    ]
    audited = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'integration.connected' AND actor_id = $2",
        tenant,
        str(hannah.user_id),
    )
    assert audited == 1
    with pytest.raises(InvalidState):  # replayed
        await svc.complete(hannah, state, "code-1")


async def test_ac12_an_expired_or_another_persons_state_is_invalid(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    hannah = await _person(db, tenant, None)
    felix = await _person(db, tenant, "security_admin")
    state = _state((await svc.start_personal(hannah, "box")).authorise_url)
    with pytest.raises(InvalidState):
        await svc.complete(felix, state, "code")  # not Felix's
    await Seeder(db.superuser_dsn).run(
        "UPDATE integration_oauth_states SET created_at = created_at - interval '11 minutes', "
        "expires_at = expires_at - interval '11 minutes' WHERE state_sha256 = $1",
        svc.state_hash(state),
    )
    with pytest.raises(InvalidState):
        await svc.complete(hannah, state, "code")  # expired


async def test_ac12_a_declined_grant_is_connect_declined(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    hannah = await _person(db, tenant, None)
    state = _state((await svc.start_personal(hannah, "box")).authorise_url)
    with pytest.raises(ConnectDeclined):
        await svc.complete(hannah, state, "declined")


async def test_ac26_a_personal_disconnect_is_the_callers_own(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    hannah = await _person(db, tenant, None)
    grace = await _person(db, tenant, "firm_admin")
    await svc.complete(
        hannah, _state((await svc.start_personal(hannah, "box")).authorise_url), "c"
    )
    with pytest.raises(NotFound):
        await svc.disconnect_personal(grace, "box")
    await svc.disconnect_personal(hannah, "box")
    seed = Seeder(db.superuser_dsn)
    assert (
        await seed.value("SELECT count(*) FROM integration_secrets WHERE tenant_id = $1", tenant)
        == 0
    )
    assert (
        await seed.value("SELECT status FROM user_integrations WHERE tenant_id = $1", tenant)
        == "disconnected"
    )


async def test_ac24_a_firm_disconnect_wants_the_typed_name_and_the_seen_version(
    db: MigratedDatabase,
) -> None:
    tenant = await _firm(db)
    felix = await _person(db, tenant, "security_admin")
    started = await svc.start_firm(felix, "karbon")
    await svc.complete(felix, _state(started.authorise_url), "c")
    seed = Seeder(db.superuser_dsn)
    version = cast(
        int,
        await seed.value(
            "SELECT version FROM firm_integrations "
            "WHERE tenant_id = $1 AND catalog_key = 'karbon'",
            tenant,
        ),
    )
    with pytest.raises(ConfirmNameMismatch):
        await svc.disconnect_firm(felix, "karbon", "karbon", version)  # the name is "Karbon"
    with pytest.raises(StaleVersion):
        await svc.disconnect_firm(felix, "karbon", "Karbon", version - 1)
    done = await svc.disconnect_firm(felix, "karbon", "Karbon", version)
    assert done.key == "karbon"
    assert (
        await seed.value("SELECT count(*) FROM integration_secrets WHERE tenant_id = $1", tenant)
        == 0
    )


async def test_ac16_a_firm_app_is_connected_at_once(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    grace = await _person(db, tenant, "firm_admin")
    started = await svc.start_firm(grace, "drata")
    assert (started.status, started.authorise_url) == ("connected", None)


async def test_ac15_a_missing_prerequisite_scope_is_refused(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    felix = await _person(db, tenant, "security_admin")
    with pytest.raises(PrerequisiteScopeMissing):
        await svc.start_firm(felix, "workstream")


async def test_ac13_a_deactivated_persons_installs_end(db: MigratedDatabase) -> None:
    tenant = await _firm(db)
    hannah = await _person(db, tenant, None)
    await svc.complete(
        hannah, _state((await svc.start_personal(hannah, "box")).authorise_url), "c"
    )
    await svc.membership_ended(
        OutboxEvent(
            uuid.uuid4(), tenant, "membership.deactivated", {"user_id": str(hannah.user_id)}
        )
    )
    seed = Seeder(db.superuser_dsn)
    assert (
        await seed.value(
            "SELECT status_reason_code FROM user_integrations WHERE tenant_id = $1", tenant
        )
        == "membership_ended"
    )
    assert (
        await seed.value("SELECT count(*) FROM integration_secrets WHERE tenant_id = $1", tenant)
        == 0
    )


async def test_ac4_a_real_firm_has_no_fakes(db: MigratedDatabase) -> None:
    tenant = await _firm(db, synthetic=False)
    felix = await _person(db, tenant, "security_admin")
    with pytest.raises(IntegrationNotAvailable):
        await svc.start_firm(felix, "karbon")


async def test_review_a_firm_state_needs_the_firm_action_still_held_at_complete(
    db: MigratedDatabase,
) -> None:
    """Security review (S46): a firm connect started by an admin is refused at the callback once
    the person no longer holds `connect_firm` (their state is spent either way)."""
    tenant = await _firm(db)
    felix = await _person(db, tenant, "security_admin")
    state = _state((await svc.start_firm(felix, "karbon")).authorise_url)
    demoted = AuthContext(felix.tenant, felix.user_id, felix.membership_id, None, felix.mfa_at)
    with pytest.raises(Forbidden):
        await svc.complete(demoted, state, "c")
    with pytest.raises(InvalidState):  # spent, so the admin cannot replay it either
        await svc.complete(felix, state, "c")
