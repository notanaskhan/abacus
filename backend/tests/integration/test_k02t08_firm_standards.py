"""K-02-T08 (TASK-2210; SPEC-500 AC-27 to AC-34; K-02 §3 F3) over HTTP against Postgres: the
firm-standards service.

The row's acceptance: Priya Raman publishes Draft v3 effective Oct 1, 2026 on the demo clock, v2
stays current until then, the audit event names her, and Daniel Reyes gets 403
not_standard_owner. Also: drafts are partners' only, the agent is refused and audited, If-Match
guards edits, the effective-date rules, discard, the diff, the examples slot and
`current_version`.

The payload values are synthetic probes shaped like an AJE thresholds version, never firm content
(AGENTS 16); the first version is inserted as a draft and published through the API.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.methodology import api as methodology_api
from abacus.modules.methodology import standards
from abacus.modules.methodology.standards_contract import ExampleRow

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

# The demo clock: Mon Sep 14, 2026, 9:24 AM CT.
DEMO = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> object:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _member(
    seed: Seeder, tenant: uuid.UUID, name: str, *, firm_role: str | None, level: str | None
) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
            "VALUES ($1, $2, $3, 'active', $4, 'staff') RETURNING id",
            tenant,
            user,
            firm_role,
            level,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    margaret: AuthContext  # quality partner: creates standards
    priya: AuthContext  # partner, the owner
    daniel: AuthContext  # partner, not the owner
    cole: AuthContext  # staff
    standard_id: uuid.UUID
    v1: uuid.UUID


def _aje(limit: int) -> dict[str, object]:
    return {
        "kind": "aje_thresholds",
        "rows": [
            {
                "account_class": "Probe class",
                "rule": "limit",
                "limit_usd": limit,
                "approver_level": "manager_or_partner",
                "batch": True,
            },
            {
                "account_class": "All other classes",
                "rule": "review_required",
                "limit_usd": None,
                "approver_level": "partner",
                "batch": False,
            },
            {
                "account_class": "Attest clients",
                "rule": "always_held",
                "limit_usd": None,
                "approver_level": "partner",
                "batch": False,
            },
        ],
    }


@pytest.fixture
def as_() -> Callable[[object], Call]:
    def bind(principal: object) -> Call:
        async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
            app = create_app()
            app.dependency_overrides[current_context] = lambda: principal
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

        return call

    return bind


@pytest.fixture
async def world(seed: Seeder, as_: Callable[[object], Call]) -> World:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'knowledge.firm_standards', 'true', 'k02-t08', 'K-02-T08')",
        tenant,
    )
    margaret = await _member(
        seed, tenant, "Margaret Okonkwo", firm_role="quality_partner", level="partner"
    )
    priya = await _member(seed, tenant, "Priya Raman", firm_role=None, level="partner")
    daniel = await _member(seed, tenant, "Daniel Reyes", firm_role=None, level="partner")
    cole = await _member(seed, tenant, "Cole Hart", firm_role=None, level="staff")
    with frozen(DEMO):
        created = await as_(margaret)(
            "POST",
            "/v1/standards",
            json={
                "kind": "aje_thresholds",
                "key": f"probe-aje-{uuid.uuid4().hex[:8]}",
                "name": "Probe AJE thresholds",
                "owner_id": str(priya.user_id),
            },
        )
    assert created.status_code == 201, created.text
    standard_id = uuid.UUID(created.json()["id"])
    payload = _aje(5000)
    v1 = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO threshold_policy_versions (tenant_id, parent_id, version, payload, "
            "payload_hash, drafted_by) VALUES ($1, $2, 1, $3::jsonb, $4, $5) RETURNING id",
            tenant,
            standard_id,
            json.dumps(payload),
            standards.payload_hash(payload),
            priya.user_id,
        ),
    )
    with frozen(DEMO):
        published = await as_(priya)(
            "POST",
            f"/v1/standards/{standard_id}/versions/{v1}/publish",
            json={"effective_from": "2026-09-14", "change_summary": "Probe v1"},
            headers={"If-Match": "1", "Idempotency-Key": uuid.uuid4().hex},
        )
    assert published.status_code == 200, published.text
    return World(tenant, margaret, priya, daniel, cole, standard_id, v1)


async def _draft(world: World, as_: Callable[[object], Call]) -> dict[str, object]:
    with frozen(DEMO):
        found = await as_(world.priya)("POST", f"/v1/standards/{world.standard_id}/versions")
    assert found.status_code == 201, found.text
    return cast(dict[str, object], found.json())


# --- AC-27: the row's acceptance ----------------------------------------------------------------


async def test_ac27_the_owner_publishes_v2_and_v1_stays_current_until_its_date(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    draft = await _draft(world, as_)
    assert draft["version"] == 2 and draft["status"] == "draft"
    assert draft["drafted_from_version_id"] == str(world.v1)
    with frozen(DEMO):
        edited = await as_(world.priya)(
            "PATCH",
            f"/v1/standards/{world.standard_id}/versions/{draft['id']}",
            json={"payload": _aje(7500), "change_summary": "Raise the probe limit"},
            headers={"If-Match": str(draft["row_version"])},
        )
        assert edited.status_code == 200, edited.text
        published = await as_(world.priya)(
            "POST",
            f"/v1/standards/{world.standard_id}/versions/{draft['id']}/publish",
            json={"effective_from": "2026-10-01", "change_summary": "Probe v2"},
            headers={
                "If-Match": str(edited.json()["row_version"]),
                "Idempotency-Key": uuid.uuid4().hex,
            },
        )
        assert published.status_code == 200, published.text
        assert published.json()["published_by"]["user_id"] == str(world.priya.user_id)
        before = (await as_(world.cole)("GET", f"/v1/standards/{world.standard_id}")).json()
    assert before["version"]["version"] == 1
    assert [(t["version"], t["status"], t["current"]) for t in before["timeline"]] == [
        (2, "published", False),
        (1, "published", True),
    ]
    with frozen(datetime(2026, 10, 1, 14, 0, tzinfo=UTC)):
        after = (await as_(world.cole)("GET", f"/v1/standards/{world.standard_id}")).json()
    assert after["version"]["version"] == 2
    assert [(t["version"], t["status"]) for t in after["timeline"]] == [
        (2, "published"),
        (1, "superseded"),
    ]
    audit = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
        "AND target_id = $3",
        world.tenant,
        "threshold_policy_version.published",
        str(draft["id"]),
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in audit] == [
        ("human", str(world.priya.user_id))
    ]
    events = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'threshold_policy.published'",
        world.tenant,
    )
    assert events == 2  # v1 in the fixture and v2 here


async def test_ac27_a_partner_who_is_not_the_owner_gets_not_standard_owner(
    world: World, as_: Callable[[object], Call]
) -> None:
    with frozen(DEMO):
        refused = await as_(world.daniel)("POST", f"/v1/standards/{world.standard_id}/versions")
    assert refused.status_code == 403
    assert refused.json()["detail"] == "not_standard_owner"
    with frozen(DEMO):
        listed = (await as_(world.daniel)("GET", "/v1/standards?kind=aje_thresholds")).json()
    mine = next(s for s in listed["items"] if s["id"] == str(world.standard_id))
    assert "firm_standard.draft" not in mine["allowed_actions"]
    assert "firm_standard.publish" not in mine["allowed_actions"]
    with frozen(DEMO):
        owner = (await as_(world.priya)("GET", "/v1/standards?kind=aje_thresholds")).json()
    theirs = next(s for s in owner["items"] if s["id"] == str(world.standard_id))
    assert {"firm_standard.draft", "firm_standard.publish"} <= set(theirs["allowed_actions"])


# --- AC-28: drafts are partners' only ------------------------------------------------------------


async def test_ac28_staff_never_see_a_draft(world: World, as_: Callable[[object], Call]) -> None:
    draft = await _draft(world, as_)
    with frozen(DEMO):
        hidden = await as_(world.cole)(
            "GET", f"/v1/standards/{world.standard_id}/versions/{draft['id']}"
        )
        listed = (await as_(world.cole)("GET", "/v1/standards")).json()
        detail = (await as_(world.cole)("GET", f"/v1/standards/{world.standard_id}")).json()
        partner = (await as_(world.daniel)("GET", "/v1/standards")).json()
    assert hidden.status_code == 404
    row = next(s for s in listed["items"] if s["id"] == str(world.standard_id))
    assert row["draft_version"] is None
    assert all(t["status"] != "draft" for t in detail["timeline"])
    theirs = next(s for s in partner["items"] if s["id"] == str(world.standard_id))
    assert theirs["draft_version"]["version"] == 2


# --- AC-29: human only -------------------------------------------------------------------------


async def test_ac29_the_agent_is_refused_and_the_refusal_is_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    agent = AuthContext(
        TenantContext(world.tenant, "agent", "agent:probe:run", world.priya.user_id),
        world.priya.user_id,
        uuid.uuid4(),
        None,
        None,
    )
    with frozen(DEMO):
        refused = await as_(agent)("POST", f"/v1/standards/{world.standard_id}/versions")
    assert refused.status_code == 403
    audited = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'decision.refused_non_human' AND target_id = $2",
        world.tenant,
        str(world.standard_id),
    )
    assert audited == 1


# --- AC-30: If-Match, not_draft, payload_invalid, draft_exists -----------------------------------


async def test_ac30_a_stale_edit_and_a_second_draft_are_refused(
    world: World, as_: Callable[[object], Call]
) -> None:
    draft = await _draft(world, as_)
    path = f"/v1/standards/{world.standard_id}/versions/{draft['id']}"
    with frozen(DEMO):
        second = await as_(world.priya)("POST", f"/v1/standards/{world.standard_id}/versions")
        stale = await as_(world.priya)(
            "PATCH", path, json={"payload": _aje(9000)}, headers={"If-Match": "99"}
        )
        invalid = await as_(world.priya)(
            "PATCH",
            path,
            json={"payload": {**_aje(9000), "rows": _aje(9000)["rows"][:2]}},  # type: ignore[index] -- a probe payload
            headers={"If-Match": str(draft["row_version"])},
        )
        frozen_v1 = await as_(world.priya)(
            "PATCH",
            f"/v1/standards/{world.standard_id}/versions/{world.v1}",
            json={"payload": _aje(9000)},
            headers={"If-Match": "2"},
        )
    assert (second.status_code, second.json()["detail"]) == (409, "draft_exists")
    assert (stale.status_code, stale.json()["detail"]) == (409, "stale_version")
    assert (invalid.status_code, invalid.json()["detail"]) == (422, "payload_invalid")
    assert (frozen_v1.status_code, frozen_v1.json()["detail"]) == (409, "not_draft")


# --- AC-31: effective dates ----------------------------------------------------------------------


async def test_ac31_backdated_or_not_after_current_is_refused(
    world: World, as_: Callable[[object], Call]
) -> None:
    draft = await _draft(world, as_)
    path = f"/v1/standards/{world.standard_id}/versions/{draft['id']}/publish"
    headers = {"If-Match": str(draft["row_version"])}
    with frozen(DEMO):
        backdated = await as_(world.priya)(
            "POST",
            path,
            json={"effective_from": "2026-09-13", "change_summary": "x"},
            headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        )
        same = await as_(world.priya)(
            "POST",
            path,
            json={"effective_from": "2026-09-14", "change_summary": "x"},
            headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
        )
    assert backdated.json()["detail"] == "effective_from_backdated"
    assert same.json()["detail"] == "effective_from_not_after_current"


# --- AC-32: discard, diff ------------------------------------------------------------------------


async def test_ac32_the_diff_names_the_changed_cells_and_discard_hides_the_draft(
    world: World, as_: Callable[[object], Call]
) -> None:
    draft = await _draft(world, as_)
    path = f"/v1/standards/{world.standard_id}/versions/{draft['id']}"
    with frozen(DEMO):
        edited = await as_(world.priya)(
            "PATCH",
            path,
            json={"payload": _aje(6200)},
            headers={"If-Match": str(draft["row_version"])},
        )
        diff = (await as_(world.priya)("GET", f"{path}/diff")).json()
        discarded = await as_(world.priya)(
            "DELETE", path, headers={"If-Match": str(edited.json()["row_version"])}
        )
        gone = await as_(world.priya)("GET", path)
        again = await as_(world.priya)("POST", f"/v1/standards/{world.standard_id}/versions")
    assert diff["against_version_id"] == str(world.v1)
    assert diff["cells"] == [{"path": "/rows/0/limit_usd", "before": "5000", "after": "6200"}]
    assert discarded.status_code == 200 and discarded.json()["status"] == "discarded"
    assert gone.status_code == 404
    assert again.status_code == 201 and again.json()["version"] == 3


# --- AC-33: the examples slot --------------------------------------------------------------------


async def test_ac33_examples_are_empty_until_a_provider_registers(
    world: World, as_: Callable[[object], Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    with frozen(DEMO):
        empty = (
            await as_(world.cole)("GET", f"/v1/standards/{world.standard_id}/examples")
        ).json()
    assert (empty["provider_registered"], empty["rows"]) == (False, [])

    async def provider(_ctx: AuthContext, _period: str | None) -> list[ExampleRow]:
        # The provider has already applied visible(): a walled client's row is simply absent.
        return [ExampleRow(None, None, "Probe entry", 120, "within_threshold", None, None)]

    monkeypatch.setitem(standards._EXAMPLES, "aje_thresholds", provider)  # pyright: ignore[reportPrivateUsage] -- the slot, registered for one test
    with frozen(DEMO):
        shown = (
            await as_(world.cole)("GET", f"/v1/standards/{world.standard_id}/examples")
        ).json()
    assert shown["provider_registered"] is True
    assert [(r["label"], r["amount_usd"]) for r in shown["rows"]] == [("Probe entry", 120)]
    assert "hidden" not in json.dumps(shown)


# --- AC-34: current_version, owner rules ---------------------------------------------------------


async def test_ac34_current_version_answers_on_a_date(world: World) -> None:
    async with _key(world) as key:
        found = await methodology_api.current_version(world.tenant, key, date(2026, 9, 30))
        assert (found.version_id, found.version) == (world.v1, 1)
        with pytest.raises(LookupError):
            await methodology_api.current_version(world.tenant, key, date(2026, 9, 13))
    with pytest.raises(LookupError):
        await methodology_api.current_version(world.tenant, "probe-none", date(2026, 9, 30))


class _key:
    """The fixture's standard key, read back."""

    def __init__(self, world: World) -> None:
        self.world = world

    async def __aenter__(self) -> str:
        detail = await standards.standard_detail(self.world.cole, self.world.standard_id, None)
        return detail.standard.key

    async def __aexit__(self, *_: object) -> None:
        return None


async def test_ac34_an_owner_must_be_a_partner(
    world: World, as_: Callable[[object], Call]
) -> None:
    with frozen(DEMO):
        refused = await as_(world.margaret)(
            "PUT",
            f"/v1/standards/{world.standard_id}/owner",
            json={"owner_id": str(world.cole.user_id)},
        )
        moved = await as_(world.margaret)(
            "PUT",
            f"/v1/standards/{world.standard_id}/owner",
            json={"owner_id": str(world.daniel.user_id)},
        )
        daniel_drafts = await as_(world.daniel)(
            "POST", f"/v1/standards/{world.standard_id}/versions"
        )
    assert (refused.status_code, refused.json()["detail"]) == (422, "owner_not_partner")
    assert moved.status_code == 200 and moved.json()["owner"]["user_id"] == str(
        world.daniel.user_id
    )
    assert daniel_drafts.status_code == 201


async def test_inv4_a_client_principal_gets_404(
    world: World, as_: Callable[[object], Call]
) -> None:
    client = AuthContext(
        TenantContext(world.tenant, "human", str(uuid.uuid4())),
        uuid.uuid4(),
        uuid.uuid4(),
        None,
        None,
        client=True,
    )
    with frozen(DEMO):
        found = await as_(client)("GET", f"/v1/standards/{world.standard_id}")
    assert found.status_code == 404
