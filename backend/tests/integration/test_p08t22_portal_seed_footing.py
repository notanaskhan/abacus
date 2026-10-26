# ac-test-author: ayushkbhatia
"""P-08-T22 (ADR-078), for P-08-T14: the footing of the portal scenario slice.

Written from the T14 row ("the branded portal host and every portal persona, with no branding or
user content in migrations or constants"; "Tess's synthetic TOTP factor"), POR-02's Figures table
(Upload 2 = the binder's open client-visible requests; Copperleaf's overdue upload, due Sep 5),
POR-01 a and d, SPEC-320 AC-15 and DEC-213. E0 is loaded with the `portal` slice into its own
database, and the figures are read the way a client reads them: Claire Feld and Tess Moreno sign
in on Brightwater Hale's portal host through the pre-session routes and read their homes over
HTTP. Expected figures are typed from the screen contracts, never imported from the scenario.

The Feld binder's figures (DEC-348, decided 2026-10-27): POR-02 a and SPEC-320 AC-15 read "19 of
21 requests done · 37 sorted", but only BND-02 a's seven requests are named anywhere, so E0 loads
those: 5 of 7 with nothing sorted (P-06 §5.4, golden-tested by P-06-T29). The handoff's figures
are a recorded gap (POR-02 Deviations). Both give Upload 2, asserted with its footing (open =
total - done).
"""

from __future__ import annotations

import ast
import re
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import date
from pathlib import Path
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.modules.identity.api import issue_sign_in_code, totp_at
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

BASE_DOMAIN = "portal-example.test"
HOST = f"brightwaterhale.{BASE_DOMAIN}"
SINK = "sink.brightwaterhale.test"
BACKEND = Path(__file__).parents[2]
PERSONAS = ("Claire Feld", "Tess Moreno", "Ben Ashby", "Meera Shah", "Sam Ortiz", "Dana Kowalski")


_LOADED: set[str] = set()


@pytest.fixture(scope="module")
def loaded(migrated_db: MigratedDatabase) -> Iterator[Database]:
    """A database of its own (the session's holds other loads); E0 goes in on first use."""
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)


@pytest.fixture(autouse=True)
async def engines(
    loaded: Database, migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", loaded.identity_url)
    monkeypatch.setenv("ABACUS_PORTAL_BASE_DOMAIN", BASE_DOMAIN)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(loaded.app_url)
    configure_relay_engine(loaded.relay_url)
    configure_portal_idp(InMemoryPortalIdp())
    if loaded.superuser_dsn not in _LOADED:
        await loader.load(loaded.superuser_dsn, "E0", slices=("portal",), wait=False)
        await Seeder(loaded.superuser_dsn).run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "SELECT $1, f, 'true', 'test-seed', 'P-08-T22' "
            "FROM unnest(ARRAY['portal.sign_in_v2', 'portal.home_v2']) f "
            "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = 'true'",
            loader.TENANT,
        )
        _LOADED.add(loaded.superuser_dsn)
    yield
    configure_portal_idp(None)
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    settings.cache_clear()


@pytest.fixture
def seed(loaded: Database) -> Seeder:
    return Seeder(loaded.superuser_dsn)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=f"https://{HOST}") as client:
        yield client


async def _session(http: httpx.AsyncClient, email: str) -> str:
    """Sign in on Brightwater Hale's host; a floor person sets up the second step."""
    headers = {"host": HOST}
    start = await http.post("/v1/portal/auth/start", json={"email": email}, headers=headers)
    assert start.status_code == 202, start.text
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None, email
    verified = await http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers=headers,
    )
    http.cookies.clear()
    assert verified.status_code == 200, verified.text
    body = verified.json()
    if body["state"] == "signed_in":
        return cast(str, body["access_token"])
    assert body["state"] == "mfa_setup_required", body
    token = body["mfa_token"]
    setup = await http.post(
        "/v1/portal/auth/mfa/setup", json={"mfa_token": token}, headers=headers
    )
    done = await http.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": totp_at(setup.json()["manual_key"], time.time())},
        headers=headers,
    )
    http.cookies.clear()
    assert done.status_code == 200, done.text
    return cast(str, done.json()["session"]["access_token"])


async def _home(http: httpx.AsyncClient, token: str) -> dict[str, object]:
    http.cookies.clear()
    response = await http.get(
        "/v1/portal/home", headers={"host": HOST, "authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def _upload(home: dict[str, object]) -> dict[str, object]:
    return next(t for t in cast(list[dict[str, object]], home["todos"]) if t["kind"] == "upload")


# --- POR-01 a: the branded host -----------------------------------------------------------------


async def test_t14_the_portal_host_is_brightwater_hales_with_its_public_branding(
    http: httpx.AsyncClient,
) -> None:
    response = await http.get("/v1/portal/branding", headers={"host": HOST})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["firm_name"] == "Brightwater Hale"
    assert body["address_line"] == "Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL"
    assert body["support_contact_name"] == "Grace Holloway"
    assert body["secured_footer"] is False
    assert "accrued" not in response.text.casefold()


# --- every portal persona -----------------------------------------------------------------------


async def test_t14_every_portal_persona_is_a_client_user_on_the_sink_domain(seed: Seeder) -> None:
    rows = await seed.rows(
        "SELECT u.display_name, u.email, m.kind FROM users u JOIN memberships m "
        "ON m.user_id = u.id AND m.tenant_id = $1 WHERE u.display_name = ANY($2::text[])",
        loader.TENANT,
        list(PERSONAS),
    )
    found = {r["display_name"]: (r["email"], r["kind"]) for r in rows}
    # Sam Ortiz has no user before he accepts (POR-01 d); everyone else is a client user.
    for name in set(PERSONAS) - {"Sam Ortiz"}:
        first, last = name.lower().split()
        assert found.get(name) == (f"{first}.{last}@{SINK}", "client"), name
    assert "Sam Ortiz" not in found


async def test_t14_sam_ortizs_invitation_delegates_nine_northwind_requests(seed: Seeder) -> None:
    [row] = await seed.rows(
        "SELECT i.email, i.status, i.kind, "
        "jsonb_array_length(i.grant_template->'scope_ids') AS n, i.created_at, i.expires_at "
        "FROM client_invitations i WHERE i.tenant_id = $1",
        loader.TENANT,
    )
    assert (row["email"], row["status"], row["kind"], row["n"]) == (
        f"sam.ortiz@{SINK}",
        "pending",
        "delegate",
        9,
    )
    assert row["created_at"].date().isoformat() == "2026-09-02"
    assert (row["expires_at"] - row["created_at"]).days == 14


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1230 (#387; a DEC-213 wait now unblocked, not escaped): "
        "the portal slice seeds no TOTP factor for Tess Moreno (P-08-T14 row; "
        "DEC-213 deferred it to P-08-T17's tables, which have landed), so POR-01 c's persona "
        "meets the setup state, not the second step"
    ),
)
async def test_t14_tess_moreno_has_her_synthetic_totp_factor(seed: Seeder) -> None:
    enrolled = await seed.value(
        "SELECT count(*) FROM mfa_factors f JOIN users u ON u.id = f.user_id "
        "WHERE u.display_name = 'Tess Moreno' AND f.enrolled_at IS NOT NULL"
    )
    assert enrolled == 1


# --- POR-02 Figures: the homes foot -------------------------------------------------------------


async def test_t14_claires_upload_2_is_her_binders_open_requests(
    http: httpx.AsyncClient,
) -> None:
    home = await _home(http, await _session(http, f"claire.feld@{SINK}"))
    scope = cast(dict[str, object], home["scope"])
    assert (scope["kind"], scope["label"]) == ("client", "Jonah & Claire Feld")
    upload = _upload(home)
    binder = cast(dict[str, int], home["binder"])
    assert upload["count"] == 2  # POR-02 a "Upload 2 documents"
    # Derived overdue (P-06): red only once the earliest open request is past due.
    due = cast(str | None, upload["due_date"])
    past = due is not None and date.fromisoformat(due) < date.today()
    assert upload["state"] == ("overdue" if past else "open"), upload
    assert binder["total"] - binder["done"] == upload["count"]  # Figures: = binder open
    assert binder["sorted_count"] >= 0


async def test_dec348_claires_binder_reads_the_loaded_5_of_7(http: httpx.AsyncClient) -> None:
    """DEC-348: the home's binder is the one E0 loads (BND-02 a), not the handoff's 19 of 21."""
    home = await _home(http, await _session(http, f"claire.feld@{SINK}"))
    binder = cast(dict[str, int], home["binder"])
    assert (binder["done"], binder["total"], binder["sorted_count"]) == (5, 7, 0)


async def test_t14_tess_morenos_copperleaf_upload_is_overdue_since_sep_5(
    http: httpx.AsyncClient,
) -> None:
    home = await _home(http, await _session(http, f"tess.moreno@{SINK}"))
    scope = cast(dict[str, object], home["scope"])
    assert (scope["kind"], scope["label"]) == ("client_entity", "Copperleaf Coffee Roasters, Inc.")
    upload = _upload(home)
    assert (upload["count"], upload["state"], upload["due_date"]) == (2, "overdue", "2026-09-05")
    # POR-02 d: red tint on the past-due to-do only.
    others = [t for t in cast(list[dict[str, object]], home["todos"]) if t["kind"] != "upload"]
    assert all(t["state"] != "overdue" for t in others)


# --- content in the database, not in code -------------------------------------------------------


def _literals(path: Path) -> Iterator[tuple[int, str]]:
    """Every string constant the code holds: not comments, not docstrings."""
    tree = ast.parse(path.read_text())
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            yield node.lineno, node.value


def test_t14_no_branding_or_person_in_migrations_or_product_constants() -> None:
    """T14: the slice's content is database rows only. The firm's display text, its address and
    its people's names appear in no migration and no product constant (comments and docstrings
    citing the artboards are not content)."""
    names = re.compile(
        "|".join(
            [
                "Brightwater Hale",
                "Brannock",
                "Grace Holloway",
                *(re.escape(p) for p in PERSONAS),
                "Copperleaf",
                "Keystone Retirement",
            ]
        ),
        re.IGNORECASE,
    )
    found = [
        f"{path.relative_to(BACKEND)}:{line}"
        for root in (BACKEND / "migrations", BACKEND / "src" / "abacus")
        for path in root.rglob("*.py")
        for line, text in _literals(path)
        if names.search(text)
    ]
    assert found == []


def test_t14_the_constant_judgement_catches_a_planted_name(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text(
        '"""Docstring naming Claire Feld."""\n# a comment naming Tess Moreno\n'
        'DISPLAY = "Brightwater Hale"\n'
    )
    assert [text for _, text in _literals(planted)] == ["Brightwater Hale"]
