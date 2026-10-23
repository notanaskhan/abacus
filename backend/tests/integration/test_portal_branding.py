"""P-08-T05 against Postgres (ADR-163 §5-§7; P-08 Story 1.1): known and unknown hosts get the same
response shape, the payload holds Public fields only and no tenant id, and the logo is served
same-origin after server-side re-encoding. Requests go through the real app with no token."""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from PIL import Image, PngImagePlugin

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.portal.branding import (
    BrandingSlots,
    LogoUnreadable,
    activate_portal_host,
    add_portal_host,
    reencode_logo,
    set_branding,
    set_logo,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

KEYS = {
    "firm_name",
    "portal_name",
    "logo_url",
    "address_line",
    "help_url",
    "privacy_url",
    "support_contact_name",
    "secured_footer",
    "sign_in",
    "maintenance_banner",
}


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _png_with_metadata() -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "someone@example.test")
    out = io.BytesIO()
    Image.new("RGB", (1600, 800), (60, 40, 30)).save(out, format="PNG", pnginfo=info)
    return out.getvalue()


async def _firm(migrated_db: MigratedDatabase, host: str, *, active: bool = True) -> uuid.UUID:
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    by = uuid.uuid4()
    async with uow(ctx) as tx:
        await set_branding(
            tx,
            tenant,
            BrandingSlots(
                display_name="Brightwater Hale",
                portal_name="Client Portal",
                address_line="200 Market Street, Minneapolis",
                help_url="https://help.example.test/portal",
                support_contact_name="Marisol Vega",
            ),
            by,
        )
        await set_logo(tx, tenant, _png_with_metadata(), by)
        await add_portal_host(tx, tenant, host, "default")
        if active:
            await activate_portal_host(tx, tenant, host)
    return tenant


async def test_p08t05_a_known_host_gets_public_slots_and_no_tenant_id(
    migrated_db: MigratedDatabase, client: httpx.AsyncClient
) -> None:
    host = f"brightwaterhale-{uuid.uuid4().hex[:8]}.portal-example.test"
    tenant = await _firm(migrated_db, host)
    answer = await client.get("/v1/portal/branding", headers={"Host": f"{host}:443"})
    assert answer.status_code == 200
    body = answer.json()
    assert set(body) == KEYS
    assert body["firm_name"] == "Brightwater Hale"
    assert body["logo_url"] == "/v1/portal/branding/logo"
    assert body["secured_footer"] is False  # off by default (ADR-163 §7)
    assert body["sign_in"] == {
        "methods": ["email_code"],
        "mfa_floor": ["owner", "signer", "approver"],
    }
    assert str(tenant) not in answer.text
    assert "accrued" not in answer.text.lower()


@pytest.mark.parametrize("host", ["unknown.portal-example.test", "not a host", ""])
async def test_p08t05_an_unknown_host_gets_the_same_shape_with_neutral_values(
    migrated_db: MigratedDatabase, client: httpx.AsyncClient, host: str
) -> None:
    await _firm(migrated_db, f"known-{uuid.uuid4().hex[:8]}.portal-example.test")
    answer = await client.get("/v1/portal/branding", headers={"Host": host})
    assert answer.status_code == 200
    body = answer.json()
    assert set(body) == KEYS
    assert body["firm_name"] is None and body["logo_url"] is None
    assert (
        await client.get("/v1/portal/branding/logo", headers={"Host": host})
    ).status_code == 404


async def test_p08t05_a_host_not_yet_verified_answers_as_unknown(
    migrated_db: MigratedDatabase, client: httpx.AsyncClient
) -> None:
    pending = f"pending-{uuid.uuid4().hex[:8]}.portal-example.test"
    await _firm(migrated_db, pending, active=False)
    body = (await client.get("/v1/portal/branding", headers={"Host": pending})).json()
    assert body["firm_name"] is None


async def test_p08t05_the_logo_is_reencoded_and_served_same_origin(
    migrated_db: MigratedDatabase, client: httpx.AsyncClient
) -> None:
    host = f"logo-{uuid.uuid4().hex[:8]}.portal-example.test"
    await _firm(migrated_db, host)
    answer = await client.get("/v1/portal/branding/logo", headers={"Host": host})
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "image/png"
    assert answer.headers["x-content-type-options"] == "nosniff"
    with Image.open(io.BytesIO(answer.content)) as served:
        assert served.format == "PNG"
        assert max(served.size) == 512
        assert "Author" not in served.info  # metadata dropped


async def test_p08t05_a_file_that_is_not_an_image_is_refused() -> None:
    for content in (b"%PDF-1.7 not an image", b"", b"GIF89a" + b"\x00" * 64):
        with pytest.raises(LogoUnreadable):
            await reencode_logo(content)


async def test_p08t05_a_logo_needs_branding_first(migrated_db: MigratedDatabase) -> None:
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    with pytest.raises(NotFound):
        async with uow(ctx) as tx:
            await set_logo(tx, tenant, _png_with_metadata(), uuid.uuid4())
