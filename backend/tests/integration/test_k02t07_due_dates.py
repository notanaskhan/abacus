"""K-02-T07 (TASK-2209; SPEC-500 AC-21 to AC-26) against Postgres: `practice.api.due_dates_for`,
`add_business_days` and `GET /v1/due-dates` over published reference sets.

The session database is shared, so every form is a unique probe and the holiday probe falls on a
date no other test uses (AGENTS 16: never a real rule).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import cast

import asyncpg
import pytest
from tests.integration.conftest import MigratedDatabase

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import AuthContext
from abacus.modules.practice import api as practice_api
from abacus.modules.practice import due_dates_routes

AY, AN = "ayushkbhatia", "notanaskhan"
Json = dict[str, object]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
async def owner(migrated_db: MigratedDatabase) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(migrated_db.owner_url.replace("postgresql+asyncpg", "postgresql"))
    try:
        yield conn
    finally:
        await conn.close()


def _probe(prefix: str) -> str:
    return f"probe.{prefix}.{uuid.uuid4().hex[:12]}"


async def _publish(
    owner: asyncpg.Connection,
    kind: str,
    payload: Json,
    *,
    effective_from: date,
    tax_year: int | None,
) -> uuid.UUID:
    raw = json.dumps(payload)
    version_id = cast(
        uuid.UUID,
        await owner.fetchval(
            "SELECT reference_set_draft($1, $2, 'Probe set', 'US', $3, NULL, $4, $5, $6::jsonb, "
            "$7, '[]'::jsonb, $3, 'probe')",
            _probe(kind),
            kind,
            AY,
            tax_year,
            effective_from,
            raw,
            "sha256:" + hashlib.sha256(raw.encode()).hexdigest(),
        ),
    )
    await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version_id, AN)
    return version_id


def _rules(form: str, *, months: int = 3, day: int = 15, ext: int | None = 6) -> Json:
    return {
        "kind": "due_date_rules",
        "rows": [
            {
                "form": form,
                "fye_rule": "calendar_year",
                "original": {"months_after_period_end": months, "day": day},
                "extension": None if ext is None else {"form": "probe-ext", "months": ext},
                "authority": "Probe authority",
            }
        ],
    }


async def test_ac26_due_dates_name_their_rules_and_hash_their_inputs(
    owner: asyncpg.Connection,
) -> None:
    form = _probe("f")[:20]
    rules = await _publish(
        owner, "due_date_rules", _rules(form), effective_from=date(2025, 1, 1), tax_year=2025
    )
    first = await practice_api.due_dates_for(form, 2025, date(2025, 12, 31))
    again = await practice_api.due_dates_for(form, 2025, date(2025, 12, 31))
    assert (first.original_due_on, first.original_rolled) == (date(2026, 3, 16), True)
    assert first.extended_due_on == date(2026, 9, 15)
    assert first.reference_set_version_ids[0] == rules
    assert first == again  # same inputs, same rules: same answer and hash
    other = await practice_api.due_dates_for(form, 2025, date(2025, 12, 31), "DC")
    assert other.inputs_hash != first.inputs_hash


async def test_ac26_a_set_naming_the_tax_year_comes_first(owner: asyncpg.Connection) -> None:
    form = _probe("f")[:20]
    ty = await _publish(
        owner,
        "due_date_rules",
        _rules(form, day=15),
        effective_from=date(2025, 1, 1),
        tax_year=2025,
    )
    await _publish(
        owner,
        "due_date_rules",
        _rules(form, day=17),
        effective_from=date(2025, 6, 1),
        tax_year=2026,
    )
    found = await practice_api.due_dates_for(form, 2025, date(2025, 12, 31))
    assert found.reference_set_version_ids[0] == ty


async def test_ac22_a_published_holiday_rolls_the_date(owner: asyncpg.Connection) -> None:
    # A probe holiday on Monday Mar 16, 2071 pushes a Sunday Mar 15 due date to Tuesday.
    form = _probe("f")[:20]
    await _publish(
        owner,
        "due_date_rules",
        _rules(form, ext=None),
        effective_from=date(2070, 1, 1),
        tax_year=2070,
    )
    holidays = await _publish(
        owner,
        "legal_holidays",
        {
            "kind": "legal_holidays",
            "rows": [{"date": "2071-03-16", "name": "Probe", "jurisdiction": "DC"}],
        },
        effective_from=date(2070, 1, 1),
        tax_year=None,
    )
    found = await practice_api.due_dates_for(form, 2070, date(2070, 12, 31))
    assert found.original_due_on == date(2071, 3, 17)
    assert holidays in found.reference_set_version_ids
    assert await practice_api.add_business_days(date(2071, 3, 13), 1) == date(2071, 3, 17)


async def test_ac23_a_covered_location_reads_the_published_postponement(
    owner: asyncpg.Connection,
) -> None:
    form = _probe("f")[:20]
    await _publish(
        owner, "due_date_rules", _rules(form), effective_from=date(2060, 1, 1), tax_year=2060
    )
    notice = f"PROBE-{uuid.uuid4().hex[:8]}"
    postponements = await _publish(
        owner,
        "disaster_postponements",
        {
            "kind": "disaster_postponements",
            "rows": [
                {
                    "notice_id": notice,
                    "areas": [{"state_code": "ZZ", "counties": ["Probe"]}],
                    "window": {"start": "2061-01-01", "end": "2061-12-31"},
                    "postponed_to": "2062-01-15",
                    "acts": ["probe"],
                }
            ],
        },
        effective_from=date(2060, 1, 1),
        tax_year=None,
    )
    covered = await practice_api.due_dates_for(
        form, 2060, date(2060, 12, 31), location=practice_api.Location("ZZ", "Probe")
    )
    assert covered.postponement_notice_id == notice
    assert covered.extended_due_on == covered.postponed_to == date(2062, 1, 15)
    assert postponements in covered.reference_set_version_ids
    plain = await practice_api.due_dates_for(form, 2060, date(2060, 12, 31))
    assert (
        plain.postponement_notice_id is None
        and postponements not in plain.reference_set_version_ids
    )


async def test_ac26_an_unknown_form_is_a_lookup_error() -> None:
    with pytest.raises(LookupError):
        await practice_api.due_dates_for(_probe("none")[:20], 2025, date(2025, 12, 31))


def _ctx(*, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        "quality_partner",
        None,
        client=client,
    )


@pytest.fixture
def open_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    async def allowed(*_: object, **__: object) -> None:
        return None

    async def enabled(_tenant: object, _flag: Flag) -> bool:
        return True

    monkeypatch.setattr(due_dates_routes, "authorise", allowed)
    monkeypatch.setattr(due_dates_routes, "flag_enabled", enabled)


@pytest.mark.usefixtures("open_gate")
async def test_ac26_the_route_serves_dates_with_provenance(owner: asyncpg.Connection) -> None:
    form = _probe("f")[:20]
    rules = await _publish(
        owner, "due_date_rules", _rules(form), effective_from=date(2025, 1, 1), tax_year=2025
    )
    out = await due_dates_routes.practice_due_dates_route(
        _ctx(), form=form, tax_year=2025, period_end=date(2025, 12, 31)
    )
    assert out.original_due_on == date(2026, 3, 16) and out.extension_form == "probe-ext"
    assert out.reference_set_version_ids[0] == rules and out.postponement is None
    with pytest.raises(NotFound):
        await due_dates_routes.practice_due_dates_route(
            _ctx(), form=_probe("none")[:20], tax_year=2025, period_end=date(2025, 12, 31)
        )


async def test_inv4_a_client_principal_gets_404() -> None:
    with pytest.raises(NotFound):
        await due_dates_routes.practice_due_dates_route(
            _ctx(client=True), form="1065", tax_year=2025, period_end=date(2025, 12, 31)
        )
