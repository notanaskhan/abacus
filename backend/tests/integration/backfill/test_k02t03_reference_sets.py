"""K-02-T03 (TASK-2102; SPEC-500 AC-8 to AC-10; K-02 US-1.1, US-1.2, US-1.4) against Postgres:
migration 0400, the global reference sets.

The row's acceptance: schema_check passes up/down/up; `abacus_app` reads published versions only
through the readers and can never write or see a draft; publishing a `standards_sets` version adds
its codes to K-01's `standards_sets` while an existing code is never deleted. Also: two people
(the approver is never the drafter), a published version is frozen, the publication log is
insert-only, and the operators' functions are owner-only.

Every value here is a synthetic probe (`probe.*` keys), never a real rule (AGENTS 16).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0400"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
AY, AN = "ayushkbhatia", "notanaskhan"


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


async def _draft(
    owner: asyncpg.Connection,
    key: str,
    kind: str,
    payload: dict[str, object],
    *,
    effective_from: date = date(2027, 1, 1),
    drafted_by: str = AY,
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await owner.fetchval(
            "SELECT reference_set_draft($1, $2, 'Probe set', 'US', $3, NULL, 2026, $4, "
            "$5::jsonb, $6, '[]'::jsonb, $7, 'probe')",
            key,
            kind,
            drafted_by,
            effective_from,
            json.dumps(payload),
            _hash(payload),
            drafted_by,
        ),
    )


def _holidays(name: str) -> dict[str, object]:
    return {
        "kind": "legal_holidays",
        "rows": [{"date": "2027-01-01", "name": name, "jurisdiction": "US"}],
    }


def test_ac10_the_migration_passes_up_down_up(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    assert sc.check(db.owner_url, db.app_url) == []


async def test_ac8_the_app_has_no_privilege_on_the_tables(db: sc.Database) -> None:
    app = await asyncpg.connect(_dsn(db.app_url))
    try:
        for statement in (
            "SELECT * FROM reference_sets",
            "SELECT * FROM reference_set_versions",
            "SELECT * FROM reference_set_publications",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.fetch(statement)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.execute(
                "INSERT INTO reference_sets (key, kind, title, content_owner) "
                "VALUES ('probe.x', 'legal_holidays', 'x', 'x')"
            )
    finally:
        await app.close()


async def test_ac10_the_operators_functions_are_owner_only(db: sc.Database) -> None:
    app = await asyncpg.connect(_dsn(db.app_url))
    try:
        for call in (
            "SELECT reference_set_publish(gen_random_uuid(), 'x', 'x')",
            "SELECT reference_set_withdraw(gen_random_uuid(), 'x', 'y', 'x')",
            "SELECT * FROM active_tenant_ids()",
            "SELECT standards_sets_apply(gen_random_uuid())",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(call)
    finally:
        await app.close()


async def test_us11_us12_a_draft_is_invisible_and_two_people_publish(db: sc.Database) -> None:
    owner = await asyncpg.connect(_dsn(db.owner_url))
    app = await asyncpg.connect(_dsn(db.app_url))
    try:
        key = f"probe.holidays.{uuid.uuid4().hex[:8]}"
        version = await _draft(owner, key, "legal_holidays", _holidays("Probe day"))
        # A draft is never served to the app.
        assert (
            await app.fetch("SELECT * FROM reference_set_resolve($1, $2)", key, date(2027, 6, 1))
            == []
        )
        assert await app.fetch("SELECT * FROM reference_set_history($1)", key) == []
        # The drafter cannot approve their own version (US-1.1).
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="approver_is_drafter"):
            await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version, AY)
        await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version, AN)
        row = await app.fetchrow(
            "SELECT * FROM reference_set_resolve($1, $2)", key, date(2027, 6, 1)
        )
        assert row is not None and row["version_id"] == version
        assert (row["drafted_by"], row["approved_by"]) == (AY, AN)
        log = await owner.fetch(
            "SELECT action, operator, approver FROM reference_set_publications "
            "WHERE version_id = $1",
            version,
        )
        assert [tuple(r) for r in log] == [("published", AY, AN)]
        # Before its effective date, nothing resolves.
        assert (
            await app.fetch("SELECT * FROM reference_set_resolve($1, $2)", key, date(2026, 12, 31))
            == []
        )
    finally:
        await app.close()
        await owner.close()


async def test_us12_the_latest_effective_version_wins_ties_to_the_highest(
    db: sc.Database,
) -> None:
    owner = await asyncpg.connect(_dsn(db.owner_url))
    app = await asyncpg.connect(_dsn(db.app_url))
    try:
        key = f"probe.form8879.{uuid.uuid4().hex[:8]}"
        payload: dict[str, object] = {
            "kind": "form_8879_set",
            "rows": [
                {
                    "return_type": "1065",
                    "tax_year": 2026,
                    "jurisdiction": "US",
                    "authorization_form": "probe-a",
                    "revision": "r1",
                }
            ],
            "tolerances": {"total_income_or_agi_usd": 1, "tax_withholding_refund_balance_usd": 1},
        }
        v1 = await _draft(owner, key, "form_8879_set", payload)
        await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", v1, AN)
        corrected = {
            **payload,
            "rows": [
                {
                    **cast(list[dict[str, object]], payload["rows"])[0],
                    "authorization_form": "probe-b",
                }
            ],
        }
        v2 = await _draft(owner, key, "form_8879_set", corrected)  # same effective date
        await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", v2, AN)
        row = await app.fetchrow(
            "SELECT * FROM reference_set_resolve($1, $2)", key, date(2027, 7, 1)
        )
        assert row is not None and row["version_id"] == v2 and row["version"] == 2
    finally:
        await app.close()
        await owner.close()


async def test_ac9_a_published_version_is_frozen_and_never_deleted(db: sc.Database) -> None:
    owner = await asyncpg.connect(_dsn(db.owner_url))
    try:
        key = f"probe.frozen.{uuid.uuid4().hex[:8]}"
        version = await _draft(owner, key, "legal_holidays", _holidays("Probe day"))
        await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version, AN)
        for statement in (
            "UPDATE reference_set_versions SET payload = '{}'::jsonb WHERE id = $1",
            "UPDATE reference_set_versions SET effective_from = '2030-01-01' WHERE id = $1",
            "UPDATE reference_set_versions SET approved_by = 'someone' WHERE id = $1",
            "DELETE FROM reference_set_versions WHERE id = $1",
        ):
            with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
                await owner.execute(statement, version)
        # The publication log is insert-only.
        with pytest.raises(asyncpg.PostgresError, match="insert-only"):
            await owner.execute(
                "UPDATE reference_set_publications SET reason = 'x' WHERE version_id = $1",
                version,
            )
        # Withdrawal is the only later move, by two other handles.
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="approver_is_operator"):
            await owner.execute("SELECT reference_set_withdraw($1, $2, $2, 'probe')", version, AY)
        await owner.execute("SELECT reference_set_withdraw($1, $2, $3, 'probe')", version, AY, AN)
        status = await owner.fetchval(
            "SELECT status FROM reference_set_versions WHERE id = $1", version
        )
        assert status == "withdrawn"
    finally:
        await owner.close()


async def test_ac9_one_draft_per_set(db: sc.Database) -> None:
    owner = await asyncpg.connect(_dsn(db.owner_url))
    try:
        key = f"probe.onedraft.{uuid.uuid4().hex[:8]}"
        await _draft(owner, key, "legal_holidays", _holidays("Probe day"))
        with pytest.raises(asyncpg.UniqueViolationError, match="draft_exists"):
            await _draft(owner, key, "legal_holidays", _holidays("Probe day 2"))
    finally:
        await owner.close()


def _sets(*rows: tuple[str, str]) -> dict[str, object]:
    return {
        "kind": "standards_sets",
        "rows": [
            {"code": code, "label": f"Probe {code}", "standard_refs": ["probe"], "family": family}
            for code, family in rows
        ],
    }


async def test_us14_publishing_standards_sets_adds_codes_and_never_deletes_one(
    db: sc.Database,
) -> None:
    owner = await asyncpg.connect(_dsn(db.owner_url))
    try:
        await owner.execute("DELETE FROM standards_sets WHERE code LIKE 'probe-%'")
        key = f"probe.standards.{uuid.uuid4().hex[:8]}"
        first = await _draft(owner, key, "standards_sets", _sets(("probe-gaas", "gaas_nonissuer")))
        await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", first, AN)
        codes = await owner.fetch(
            "SELECT code, family FROM standards_sets WHERE code LIKE 'probe-%'"
        )
        assert {(r["code"], r["family"]) for r in codes} == {("probe-gaas", "gaas_nonissuer")}

        second = await _draft(
            owner,
            key,
            "standards_sets",
            _sets(("probe-gaas", "gaas_nonissuer"), ("probe-sqms", "sqms")),
        )
        await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", second, AN)
        codes = await owner.fetch("SELECT code FROM standards_sets WHERE code LIKE 'probe-%'")
        assert {r["code"] for r in codes} == {"probe-gaas", "probe-sqms"}

        # A version that drops a code, or moves one to another family, is refused whole.
        dropped = await _draft(owner, key, "standards_sets", _sets(("probe-sqms", "sqms")))
        with pytest.raises(asyncpg.CheckViolationError, match="code_removed"):
            await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", dropped, AN)
        codes = await owner.fetch("SELECT code FROM standards_sets WHERE code LIKE 'probe-%'")
        assert {r["code"] for r in codes} == {"probe-gaas", "probe-sqms"}
    finally:
        await owner.close()


async def test_us14_an_issuer_family_is_refused(db: sc.Database) -> None:
    owner = await asyncpg.connect(_dsn(db.owner_url))
    try:
        key = f"probe.issuer.{uuid.uuid4().hex[:8]}"
        rows = _sets(("probe-pcaob", "pcaob"))
        version = await _draft(owner, key, "standards_sets", rows)
        with pytest.raises(asyncpg.CheckViolationError, match="family_not_allowed"):
            await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version, AN)
    finally:
        await owner.close()
