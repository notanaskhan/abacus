"""K-02-T05 (TASK-2208; SPEC-500 AC-15 to AC-20; K-02 §4.3 to §4.5) against Postgres: the
reference-set service, its typed readers and `/v1/reference-sets`.

The row's acceptance: a re-published correction wins for its effective date, the prior tax year's
set answers before that date, every response names its version id, and a `standards_sets` draft
holding a PCAOB or issuer set, or removing an existing code, is refused (X-07).

The session database is shared, so every key, return type, form and record type is a unique
synthetic probe (AGENTS 16: never a real rule).
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
from abacus.modules.platform import api as platform_api
from abacus.modules.platform import reference_sets, reference_sets_routes
from abacus.modules.platform.reference_sets_contract import StandardsSetsPayload

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
    # Short enough for every payload field it lands in (a return type is at most 20 characters).
    return f"probe.{prefix}.{uuid.uuid4().hex[:8]}"


def _hash(payload: Json) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def _publish(
    owner: asyncpg.Connection,
    key: str,
    kind: str,
    payload: Json,
    *,
    effective_from: date,
    tax_year: int | None = 2026,
) -> uuid.UUID:
    """Draft (AY) and publish (AN) one version: the two-person rule, as the CLI will."""
    version_id = cast(
        uuid.UUID,
        await owner.fetchval(
            "SELECT reference_set_draft($1, $2, 'Probe set', 'US', $3, NULL, $4, $5, $6::jsonb, "
            "$7, '[{\"label\": \"Probe source — verify\"}]'::jsonb, $3, 'probe')",
            key,
            kind,
            AY,
            tax_year,
            effective_from,
            json.dumps(payload),
            _hash(payload),
        ),
    )
    await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version_id, AN)
    return version_id


def _form_set(return_type: str, form: str, *, agi: int = 25, balance: int = 14) -> Json:
    return {
        "kind": "form_8879_set",
        "rows": [
            {
                "return_type": return_type,
                "tax_year": 2026,
                "jurisdiction": "US",
                "authorization_form": form,
                "revision": "probe",
            }
        ],
        "tolerances": {
            "total_income_or_agi_usd": agi,
            "tax_withholding_refund_balance_usd": balance,
        },
    }


# --- AC-15: a correction wins from its own effective date; the prior set answers before it -------


async def test_ac15_a_correction_with_the_same_effective_date_wins(
    owner: asyncpg.Connection,
) -> None:
    # K-02 §2: v1 effective 2027-01-01 and a correction v2 with the same date; v2 answers.
    key, return_type = _probe("f8879"), _probe("rt")
    v1 = await _publish(
        owner,
        key,
        "form_8879_set",
        _form_set(return_type, "probe-a"),
        effective_from=date(2027, 1, 1),
    )
    v2 = await _publish(
        owner,
        key,
        "form_8879_set",
        _form_set(return_type, "probe-b"),
        effective_from=date(2027, 1, 1),
    )
    found = await platform_api.form_8879_for(return_type, 2026, "US", as_of=date(2027, 7, 1))
    assert found.authorization_form == "probe-b"
    assert found.reference_set_version_id == v2 != v1


async def test_ac15_the_prior_set_answers_before_the_corrections_date(
    owner: asyncpg.Connection,
) -> None:
    key = _probe("holidays")
    prior = await _publish(
        owner,
        key,
        "legal_holidays",
        {
            "kind": "legal_holidays",
            "rows": [{"date": "2026-01-01", "name": "Prior", "jurisdiction": "US"}],
        },
        effective_from=date(2026, 1, 1),
        tax_year=2025,
    )
    later = await _publish(
        owner,
        key,
        "legal_holidays",
        {
            "kind": "legal_holidays",
            "rows": [{"date": "2027-01-01", "name": "Later", "jurisdiction": "US"}],
        },
        effective_from=date(2027, 1, 1),
    )
    before = await platform_api.reference_value(key, date(2026, 12, 31))
    on = await platform_api.reference_value(key, date(2027, 1, 1))
    assert (before.version_id, before.version) == (prior, 1)
    assert (on.version_id, on.version) == (later, 2)
    assert on.kind == "legal_holidays" and on.effective_from == date(2027, 1, 1)


async def test_ac15_nothing_in_effect_is_a_lookup_error(owner: asyncpg.Connection) -> None:
    key = _probe("holidays")
    await _publish(
        owner,
        key,
        "legal_holidays",
        {
            "kind": "legal_holidays",
            "rows": [{"date": "2027-01-01", "name": "Only", "jurisdiction": "US"}],
        },
        effective_from=date(2027, 1, 1),
    )
    with pytest.raises(LookupError):
        await platform_api.reference_value(key, date(2026, 6, 30))
    with pytest.raises(LookupError):
        await platform_api.reference_value(_probe("unknown"), date(2027, 6, 30))


async def test_ac16_a_draft_is_never_served(owner: asyncpg.Connection) -> None:
    key = _probe("draft")
    payload: Json = {
        "kind": "legal_holidays",
        "rows": [{"date": "2027-01-01", "name": "Draft", "jurisdiction": "US"}],
    }
    await owner.fetchval(
        "SELECT reference_set_draft($1, 'legal_holidays', 'Probe', 'US', $2, NULL, 2026, "
        "'2020-01-01', $3::jsonb, $4, '[]'::jsonb, $2, 'probe')",
        key,
        AY,
        json.dumps(payload),
        _hash(payload),
    )
    with pytest.raises(LookupError):
        await platform_api.reference_value(key, date(2027, 6, 30))
    assert await reference_sets.versions(key) is None
    assert key not in {s.key for s in await reference_sets.list_sets("legal_holidays")}


# --- AC-17: every typed reader names the version its answer came from ----------------------------


async def test_ac17_the_tolerances_name_their_version(owner: asyncpg.Connection) -> None:
    return_type = _probe("rt")
    version = await _publish(
        owner,
        _probe("f8879"),
        "form_8879_set",
        _form_set(return_type, "probe-c", agi=31, balance=17),
        effective_from=date(2020, 1, 1),
    )
    form = await platform_api.form_8879_for(return_type, 2026, "US", as_of=date(2027, 7, 1))
    assert form.reference_set_version_id == version
    with pytest.raises(LookupError):
        await platform_api.form_8879_for(return_type, 2026, "DC", as_of=date(2027, 7, 1))


async def test_ac17_thresholds_and_retention_floors_name_their_version(
    owner: asyncpg.Connection,
) -> None:
    form, record = _probe("1099"), _probe("record")
    thresholds = await _publish(
        owner,
        _probe("thresholds"),
        "information_return_thresholds",
        {
            "kind": "information_return_thresholds",
            "rows": [
                {
                    "form": form[:20],
                    "payment_year": 2026,
                    "threshold_usd": 7,
                    "min_transactions": None,
                }
            ],
        },
        effective_from=date(2020, 1, 1),
    )
    floors = await _publish(
        owner,
        _probe("retention"),
        "retention_minimums",
        {
            "kind": "retention_minimums",
            "rows": [
                {
                    "record_type": record,
                    "service_line": "probe",
                    "floor_years": 3,
                    "anchor": "probe_anchor",
                    "authority": "Probe authority",
                }
            ],
        },
        effective_from=date(2020, 1, 1),
        tax_year=None,
    )
    threshold = await platform_api.information_return_threshold(form[:20], 2026)
    floor = await platform_api.retention_minimum(record, "probe")
    assert (threshold.threshold_usd, threshold.reference_set_version_id) == (7, thresholds)
    assert (floor.floor_years, floor.reference_set_version_id) == (3, floors)


# --- AC-18: the routes ---------------------------------------------------------------------------


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

    monkeypatch.setattr(reference_sets_routes, "authorise", allowed)
    monkeypatch.setattr(reference_sets_routes, "flag_enabled", enabled)


@pytest.mark.usefixtures("open_gate")
async def test_ac18_the_routes_resolve_list_and_name_versions(owner: asyncpg.Connection) -> None:
    key = _probe("holidays")
    payload: Json = {
        "kind": "legal_holidays",
        "rows": [{"date": "2026-01-01", "name": "Probe", "jurisdiction": "DC"}],
    }
    v1 = await _publish(owner, key, "legal_holidays", payload, effective_from=date(2020, 1, 1))
    resolved = await reference_sets_routes.resolve_reference_set_route(
        key, _ctx(), as_of=date(2026, 6, 30)
    )
    assert resolved.version.id == v1
    assert resolved.version.drafted_by == AY and resolved.version.approved_by == AN
    assert resolved.version.source_citations[0].label == "Probe source — verify"
    assert resolved.set.current_version == 1
    listed = await reference_sets_routes.list_reference_sets_route(_ctx(), kind="legal_holidays")
    assert key in {s.key for s in listed.items}
    history = await reference_sets_routes.reference_set_versions_route(key, _ctx())
    assert [v.id for v in history.items] == [v1]
    assert history.items[0].status == "published"


@pytest.mark.usefixtures("open_gate")
async def test_ac18_an_unknown_key_or_nothing_in_effect_is_404() -> None:
    with pytest.raises(NotFound):
        await reference_sets_routes.resolve_reference_set_route(
            _probe("nothing"), _ctx(), as_of=date(2027, 1, 1)
        )
    with pytest.raises(NotFound):
        await reference_sets_routes.reference_set_versions_route(_probe("nothing"), _ctx())


async def test_inv4_a_client_principal_gets_404_before_the_matrix() -> None:
    with pytest.raises(NotFound):
        await reference_sets_routes.list_reference_sets_route(_ctx(client=True), kind=None)


# --- AC-19: standards_sets drafts (X-07) --------------------------------------------------------


def _standards(*rows: tuple[str, str, str]) -> Json:
    return {
        "kind": "standards_sets",
        "rows": [
            {"code": code, "label": label, "standard_refs": [], "family": family}
            for code, label, family in rows
        ],
    }


async def test_ac19_a_standards_draft_dropping_a_published_code_is_refused(
    owner: asyncpg.Connection,
) -> None:
    keep, drop = f"probe-{uuid.uuid4().hex[:8]}", f"probe-{uuid.uuid4().hex[:8]}"
    await _publish(
        owner,
        _probe("standards"),
        "standards_sets",
        _standards((keep, "Probe GAAS", "gaas_nonissuer"), (drop, "Probe SSARS", "ssars")),
        effective_from=date(2020, 1, 1),
    )
    with pytest.raises(platform_api.StandardsSetRefused) as removed:
        await platform_api.check_draft(
            "standards_sets", _standards((keep, "Probe GAAS", "gaas_nonissuer"))
        )
    assert removed.value.facts["reason"] == "code_removed"
    with pytest.raises(platform_api.StandardsSetRefused) as moved:
        await platform_api.check_draft(
            "standards_sets",
            _standards((keep, "Probe GAAS", "ssars"), (drop, "Probe SSARS", "ssars")),
        )
    assert moved.value.facts["reason"] == "family_changed"


async def test_ac19_a_pcaob_or_issuer_set_is_refused() -> None:
    for row in (
        ("pcaob-as", "PCAOB auditing standards", "gaas_nonissuer"),
        ("as-2201", "Audit of internal control", "gaas_nonissuer"),
        ("issuer-audits", "Issuer audits", "gaas_nonissuer"),
    ):
        parsed = reference_sets.validate_payload("standards_sets", _standards(row))
        assert isinstance(parsed, StandardsSetsPayload)
        with pytest.raises(platform_api.StandardsSetRefused) as refused:
            reference_sets.validate_standards_sets(parsed, {})
        assert refused.value.facts["reason"] == "excluded_family"
    with pytest.raises(platform_api.ReferencePayloadInvalid):
        reference_sets.validate_payload("standards_sets", _standards(("pcaob", "PCAOB", "pcaob")))


async def test_ac17_references_in_effect_lists_every_set_of_the_kind_on_the_date(
    owner: asyncpg.Connection,
) -> None:
    key = _probe("rules")
    payload: Json = {
        "kind": "retention_minimums",
        "rows": [
            {
                "record_type": _probe("record"),
                "service_line": "probe",
                "floor_years": 1,
                "anchor": "probe_anchor",
                "authority": "Probe authority",
            }
        ],
    }
    version = await _publish(
        owner, key, "retention_minimums", payload, effective_from=date(2020, 1, 1), tax_year=2025
    )
    found = {
        r.key: r
        for r in await platform_api.references_in_effect("retention_minimums", date(2026, 1, 1))
    }
    assert (found[key].version_id, found[key].tax_year) == (version, 2025)
    early = await platform_api.references_in_effect("retention_minimums", date(2019, 12, 31))
    assert key not in {r.key for r in early}
