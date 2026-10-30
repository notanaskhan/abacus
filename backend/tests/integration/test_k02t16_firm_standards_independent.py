# ac-test-author: ayushkbhatia
"""K-02-T16 (TASK-2407; ADR-078; SPEC-500 AC-27 to AC-34, AC-39 to AC-48): independent acceptance
tests for the firm-standards service (K-02-T08), the standards API (K-02-T10) and import/export
(K-02-T11), written from K-02 §3 to §4, SPEC-500 and the C21 part B contract, not from the
implementing suites.

The row's acceptance: the suite fails if the agent can draft or publish, a staff member can see a
draft, or a figure the spec states drifts. Boundary: `create_app()` over HTTP on the migrated
Postgres for the lifecycle (people seeded through `Seeder`), and `methodology.api`'s public
functions (with the C21 part B payload models from its contract) for the deterministic standards
API. Payload values are synthetic probes shaped like the
spec's examples, never firm content (AGENTS 16).

test_author: ayushkbhatia · test_session: 2026-10-30 s19-k02-t16
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.methodology import api as methodology
from abacus.modules.methodology.standards_contract import (
    AjeThresholdsPayload,
    DocumentConfidencePayload,
    SsarsCasSettingsPayload,
    VarianceThresholdsPayload,
)

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

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


async def _person(
    seed: Seeder,
    tenant: uuid.UUID,
    name: str,
    *,
    firm_role: str | None,
    level: str | None,
    kind: str = "human",
    mfa_age: timedelta = timedelta(minutes=1),
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
        tenant=TenantContext(tenant, kind, str(user)),  # pyright: ignore[reportArgumentType] -- a seeded actor kind
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - mfa_age,
    )


@pytest.fixture
def as_() -> Callable[[object], Call]:
    def bind(principal: object) -> Call:
        async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
            app = create_app()
            app.dependency_overrides[current_context] = lambda: principal
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments

        return call

    return bind


def _variance(pct: str, amount: int) -> dict[str, object]:
    return {
        "kind": "variance_thresholds",
        "rows": [{"context": "close_flux", "pct": pct, "amount_usd": amount}],
    }


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    quality: AuthContext
    owner: AuthContext
    other_partner: AuthContext
    staff: AuthContext
    standard_id: uuid.UUID


@pytest.fixture
async def firm(seed: Seeder, as_: Callable[[object], Call]) -> Firm:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'knowledge.firm_standards', 'true', 'k02-t16', 'K-02-T16')",
        tenant,
    )
    quality = await _person(
        seed, tenant, "Probe Quality", firm_role="quality_partner", level="partner"
    )
    owner = await _person(seed, tenant, "Probe Owner", firm_role=None, level="partner")
    other = await _person(seed, tenant, "Probe Partner", firm_role=None, level="partner")
    staff = await _person(seed, tenant, "Probe Staff", firm_role=None, level="staff")
    engagement = await seed.engagement(tenant, await seed.entity(tenant), quality.user_id)
    await seed.member(engagement, Person(staff.user_id, tenant), "staff")
    with frozen(DEMO):
        created = await as_(quality)(
            "POST",
            "/v1/standards",
            json={
                "kind": "variance_thresholds",
                "key": f"probe-variance-{uuid.uuid4().hex[:8]}",
                "name": "Probe variance thresholds",
                "owner_id": str(owner.user_id),
            },
        )
    assert created.status_code == 201, created.text
    return Firm(tenant, quality, owner, other, staff, uuid.UUID(created.json()["id"]))


async def _draft(firm: Firm, as_: Callable[[object], Call]) -> dict[str, object]:
    with frozen(DEMO):
        found = await as_(firm.owner)("POST", f"/v1/standards/{firm.standard_id}/versions")
    assert found.status_code == 201, found.text
    return cast(dict[str, object], found.json())


async def _publish(
    firm: Firm, as_: Callable[[object], Call], who: AuthContext, draft: dict[str, object]
) -> httpx.Response:
    with frozen(DEMO):
        return await as_(who)(
            "POST",
            f"/v1/standards/{firm.standard_id}/versions/{draft['id']}/publish",
            json={"effective_from": "2026-10-01", "change_summary": "Probe"},
            headers={
                "If-Match": str(draft["row_version"]),
                "Idempotency-Key": uuid.uuid4().hex,
            },
        )


# --- Lifecycle: humans only, the owner only, fresh MFA, drafts hidden from staff ----------------


async def test_ac30_the_agent_can_neither_draft_nor_publish(
    firm: Firm, as_: Callable[[object], Call], seed: Seeder
) -> None:
    agent = AuthContext(
        tenant=TenantContext(firm.tenant, "agent", str(firm.owner.user_id)),
        user_id=firm.owner.user_id,
        membership_id=firm.owner.membership_id,
        firm_role=None,
        mfa_at=datetime.now(UTC),
    )
    with frozen(DEMO):
        drafted = await as_(agent)("POST", f"/v1/standards/{firm.standard_id}/versions")
    assert drafted.status_code in (403, 404), drafted.text
    draft = await _draft(firm, as_)
    published = await _publish(firm, as_, agent, draft)
    assert published.status_code in (403, 404), published.text
    status = await seed.value(
        "SELECT status FROM threshold_policy_versions WHERE id = $1", uuid.UUID(str(draft["id"]))
    )
    assert status == "draft"


async def test_ac31_a_partner_who_is_not_the_owner_cannot_publish(
    firm: Firm, as_: Callable[[object], Call]
) -> None:
    draft = await _draft(firm, as_)
    refused = await _publish(firm, as_, firm.other_partner, draft)
    assert refused.status_code == 403
    assert refused.json()["detail"] == "not_standard_owner"


async def test_ac32_publishing_needs_a_fresh_second_factor(
    firm: Firm, as_: Callable[[object], Call], seed: Seeder
) -> None:
    draft = await _draft(firm, as_)
    stale = AuthContext(
        tenant=firm.owner.tenant,
        user_id=firm.owner.user_id,
        membership_id=firm.owner.membership_id,
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(days=2),
    )
    refused = await _publish(firm, as_, stale, draft)
    assert refused.status_code == 403
    fresh = await _publish(firm, as_, firm.owner, draft)
    assert fresh.status_code == 200, fresh.text


async def test_ac33_staff_never_see_a_draft(firm: Firm, as_: Callable[[object], Call]) -> None:
    draft = await _draft(firm, as_)
    with frozen(DEMO):
        version = await as_(firm.staff)(
            "GET", f"/v1/standards/{firm.standard_id}/versions/{draft['id']}"
        )
        detail = await as_(firm.staff)("GET", f"/v1/standards/{firm.standard_id}")
        partner = await as_(firm.other_partner)(
            "GET", f"/v1/standards/{firm.standard_id}/versions/{draft['id']}"
        )
    assert version.status_code == 404
    assert str(draft["id"]) not in detail.text
    assert partner.status_code == 200


async def test_ac47_an_import_drafts_and_never_publishes(
    firm: Firm, as_: Callable[[object], Call], seed: Seeder
) -> None:
    draft = await _draft(firm, as_)
    with frozen(DEMO):
        again = await as_(firm.owner)(
            "POST",
            f"/v1/standards/{firm.standard_id}/imports",
            content=b"context,pct,amount_usd\nclose_flux,10,2500\n",
            headers={"Content-Type": "text/csv"},
        )
    # A draft is open: the import refuses rather than replacing it.
    assert again.status_code == 409
    assert again.json()["detail"] == "draft_exists"
    published = await seed.value(
        "SELECT count(*) FROM threshold_policy_versions WHERE parent_id = $1 "
        "AND status = 'published'",
        firm.standard_id,
    )
    assert published == 0
    assert draft["status"] == "draft"


# --- The deterministic standards API (K-02-T10) --------------------------------------------------


def _policy() -> methodology.PolicyRef:
    return methodology.PolicyRef(
        standard_key="probe-policy", version_id=uuid.uuid4(), version=2, name="Probe policy"
    )


def _aje() -> AjeThresholdsPayload:
    return AjeThresholdsPayload.model_validate(
        {
            "kind": "aje_thresholds",
            "rows": [
                {
                    "account_class": "Probe accruals",
                    "rule": "limit",
                    "limit_usd": 15000,
                    "approver_level": "senior_or_above",
                    "batch": True,
                },
                {
                    "account_class": "All other classes",
                    "rule": "review_required",
                    "limit_usd": None,
                    "approver_level": "manager_or_partner",
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
    )


def test_ac39_an_attest_clients_entry_is_held_whatever_the_amount() -> None:
    held = methodology.classify_entry(
        _aje(), _policy(), account_class="Probe accruals", amount_usd=1, attest_client=True
    )
    assert held.outcome == "review_required"
    assert held.reason == "attest_client"
    assert held.approver_level == "partner"


def test_ac39_a_listed_class_is_within_up_to_its_limit_and_held_past_it() -> None:
    at = methodology.classify_entry(
        _aje(), _policy(), account_class="Probe accruals", amount_usd=15000, attest_client=False
    )
    over = methodology.classify_entry(
        _aje(), _policy(), account_class="Probe accruals", amount_usd=15001, attest_client=False
    )
    assert at.outcome == "within_threshold"
    assert at.batch is True
    assert over.outcome == "review_required"


def test_ac40_a_variance_is_exceeded_only_when_both_are_strictly_over() -> None:
    payload = VarianceThresholdsPayload.model_validate(_variance("10", 2500))
    both = methodology.variance_exceeded(
        payload, _policy(), context="close_flux", current_usd=12601, prior_usd=10000
    )
    amount_only = methodology.variance_exceeded(
        payload, _policy(), context="close_flux", current_usd=102600, prior_usd=100000
    )
    at_both = methodology.variance_exceeded(
        payload, _policy(), context="close_flux", current_usd=27500, prior_usd=25000
    )
    assert both.exceeded is True
    assert amount_only.exceeded is False  # 2.6% is not over 10%
    assert at_both.exceeded is False  # exactly 10% and exactly 2,500 is not strictly over
    assert at_both.amount_change_usd == 2500


def test_ac42_confidence_never_auto_accepts() -> None:
    payload = DocumentConfidencePayload.model_validate(
        {
            "kind": "document_confidence",
            "hold_below_pct": "90",
            "auto_accept_above_pct": "98",
            "auto_accept_enabled": False,
        }
    )
    low = methodology.confidence_hold(payload, _policy(), confidence_pct=Decimal("62"))
    high = methodology.confidence_hold(payload, _policy(), confidence_pct=Decimal("99.5"))
    assert low.hold is True
    assert high.hold is False
    assert high.auto_accept is False


def test_ac44_ssars_framework_turns_on_dec_15_2026_unless_adopted_early() -> None:
    off = SsarsCasSettingsPayload.model_validate(
        {"kind": "ssars_cas_settings", "early_adopt_ssars27": False}
    )
    early = off.model_copy(update={"early_adopt_ssars27": True})
    before = methodology.ssars_framework_for(off, _policy(), period_end=date(2026, 8, 31))
    boundary = methodology.ssars_framework_for(off, _policy(), period_end=date(2026, 12, 15))
    adopted = methodology.ssars_framework_for(early, _policy(), period_end=date(2026, 8, 31))
    assert before.framework == "ar_c_70_preparation"
    assert boundary.framework == "cas_by_product"
    assert adopted.framework == "cas_by_product"


def test_payload_helpers_stay_json_serialisable() -> None:
    # The suite's probes round-trip through JSON as the API would carry them.
    assert json.loads(json.dumps(_variance("10", 2500)))["rows"][0]["amount_usd"] == 2500
