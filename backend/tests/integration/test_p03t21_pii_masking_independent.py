# ac-test-author: ayushkbhatia
"""SPEC-322 AC-23 to AC-29, AC-31 to AC-35, AC-40 (P-03-T21, TASK-1322): PII is detected on every
form of the synthetic corpus, every served page image is opaque inside every detected region,
agents read only masked material, and a value is revealed only by the people the matrix names,
logged without the value. A password PDF unlocks into derived records without changing the
evidence.

Complements the P-03-T18 suite (`backfill/test_p03t18_citations_viewer_independent.py`), which
holds the W-2 sealed region, the viewer page's burn, the offshore text view, the generic refused
reveal, the MFA step-up on an SSN and the 21st reveal. This file adds: recall over the whole
corpus, pixels of every page route that serves an image, the agent readers of `evidence.api`, the
full `pii.reveal` matrix with nothing written on refusal, the audit sinks of an EIN and an SSN
reveal on other forms, and the unlock (C4 §3.5).

Boundary: `create_app()` over HTTP as the firm's people and the client's, on the migrated
Postgres and the compose S3 image. Uploads go through the client upload route and the steps a v7
upload run takes (extract, check, words, PII scan, masked preview), as T18 runs them. Agent
material is read through the public `evidence.api.review_material` and `match_material`, as the
upload reviewer and the matcher do (system context of the upload run).

Later decisions followed instead of the spec's words: DEC-370 (MFA for every kind; a refusal
other than `mfa_required` is the plain `{"detail": "forbidden"}`; visibility answers 404 before
`authorise`), DEC-369 (the legacy page routes serve the masked rendition), DEC-425 (unlock as a
derivation; a wrong password is 200 `wrong_password`; a second unlock is 409
`not_password_protected`).
"""

from __future__ import annotations

import io
import json
import re
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest
from PIL import Image
from types_boto3_s3 import S3Client

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
)
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.tin_patterns import has_tin
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    UPLOAD_INBOX,
    UPLOAD_VERSION,
    UploadInput,
    add_to_inbox,
    check_upload_content,
    masked_preview_upload,
    match_material,
    pii_scan_upload,
    review_material,
    words_upload,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.identity.api import AuthContext, configure_verifier, reset_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.synthetic.documents import (
    form_1099_pdf,
    k1_pdf,
    password_pdf,
    pii_corpus,
    w2_pdf,
)

from .backfill.support import Migrated, Net, Person, Role, Seeder, Site

BUCKET: Final = "task1322-pii-masking"
MASTER: Final = b"task1322-pii-masking-master-key-0123456789"
PDF: Final = "application/pdf"
FORBIDDEN: Final = {"detail": "forbidden"}
NOT_FOUND: Final = {"detail": "not found"}
FLAGS: Final = (
    "uploads.processing",
    "evidence.citations_v2",
    "evidence.viewer_v1",
    "evidence.pii_reveal",
    "evidence.viewer_unlock",
)
# The corpus, typed from its forms (P-03 §4.4; DEC-322): (page, kind, last four).
EXPECTED: Final[dict[str, frozenset[tuple[int, str, str | None]]]] = {
    "W-2": frozenset({(1, "ssn", "6081"), (1, "ein", "0287")}),
    "K-1": frozenset({(1, "ein", "7890"), (1, "ssn", "4412")}),
    "1099-INT": frozenset({(1, "ein", "4321"), (1, "ssn", "3456"), (1, "bank_account", "2291")}),
    "Direct deposit": frozenset(
        {(1, "routing_number", "0001"), (1, "bank_account", "7731"), (1, "dob", None)}
    ),
}
CORPUS: Final = tuple(EXPECTED)
# Display tokens (P-03 §4.4): the routing number has none in the spec, so only its last four.
TOKENS: Final = {
    "ssn": "•••-••-{last4}",
    "ein": "••-•••{last4}",
    "bank_account": "••••{last4}",
    "dob": "••/••/••••",
}
# The clear values the forms print (synthetic: 000- and 9xx areas, the never-assigned 00 prefix).
W2_SSN: Final = "000-00-6081"
W2_EIN: Final = "00-1230287"
K1_EIN: Final = "00-4567890"
F1099_SSN: Final = "900-12-3456"
F1099_EIN: Final = "00-7654321"
F1099_ACCOUNT: Final = "SYN-4410-2291"
UNLABELLED: Final = "000-00-1111"
OPENS_WITH: Final = "halvard-2025-synthetic"
NOT_IT: Final = "not-the-password"
TIN_SHAPES: Final = (
    re.compile(r"\d{3}-\d{2}-\d{4}"),
    re.compile(r"\d{2}-\d{7}"),
    re.compile(r"(?<!\d)\d{9}(?!\d)"),
)
# Every form prints its first label at x 36, baseline 740 on a 792 pt page: ink is there.
LABEL_BOX: Final = (36.0, 44.0, 100.0, 54.0)
# The direct-deposit form prints its unlabelled reference line at baseline 640 (top about 142).
REFERENCE_BAND: Final = (132.0, 160.0)


# --- Wiring (as `backfill/conftest.py`, which this directory does not inherit) -------------------


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    forget_flags()
    yield
    forget_flags()
    storage.reset_storage()
    reset_key_service()


# --- The world: one firm, one engagement, its people ------------------------------------------


async def _rendered(given: UploadInput) -> None:
    """The steps a v7 upload run takes (DEC-369): extract, check, words, PII scan, masked page."""
    await extract_upload(given)
    await check_upload_content(given)
    await words_upload(given)
    await pii_scan_upload(given)
    await masked_preview_upload(given)


def _person(who: Person) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _flags(seed: Seeder, tenant_id: uuid.UUID) -> None:
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1322')",
            tenant_id,
            flag,
        )


async def _member(seed: Seeder, site: Site, role: str) -> Person:
    """An engagement member in `role`, with confirmed independence (any role the table takes)."""
    who = await seed.person(site.tenant_id)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
        role,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
        "clock_timestamp()) ON CONFLICT DO NOTHING",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
    )
    return who


@dataclass(frozen=True)
class Upload:
    version: uuid.UUID
    item: uuid.UUID
    content: bytes


@dataclass(frozen=True)
class World:
    net: Net
    tenant_id: uuid.UUID
    owner: Person
    samuel: Person  # onshore staff
    rhea: Person  # reviewer: reads evidence, may neither reveal nor unlock
    client: Person  # the client's admin
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "evidence.upload_processing")

    async def upload(self, content: bytes) -> Upload:
        """The client's upload of `content` to a new request item, rendered as a v7 run."""
        item = await self.seed.item(self.site, f"Document {uuid.uuid4().hex[:6]}")
        response = await self.net.http.post(
            f"/v1/engagements/{self.site.engagement_id}/request-items/{item}/uploads",
            params={"filename": "document.pdf"},
            content=content,
            headers={**self.net.headers(self.client), "Content-Type": PDF},
        )
        assert response.status_code == 201, response.text
        version = uuid.UUID(response.json()["evidence_version_id"])
        await _rendered(UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(version)))
        return Upload(version, item, content)

    async def manifest(self, version: uuid.UUID, who: Person | None = None) -> dict[str, object]:
        response = await self.net.call(
            "GET", f"/v1/evidence-versions/{version}/viewer", who or self.samuel
        )
        assert response.status_code == 200, response.text
        return cast(dict[str, object], response.json())

    async def masks(self, version: uuid.UUID) -> list[dict[str, object]]:
        return cast(list[dict[str, object]], (await self.manifest(version))["pii_masks"])

    async def mask_id(self, version: uuid.UUID, kind: str) -> str:
        [found] = [m for m in await self.masks(version) if m["kind"] == kind]
        return str(found["id"])

    async def reveal(
        self, version: uuid.UUID, region: str, who: Person, *, mfa: bool = True
    ) -> httpx.Response:
        return await self.net.call(
            "POST",
            f"/v1/evidence-versions/{version}/pii-reveals",
            who,
            body={"region_id": region},
            mfa=mfa,
        )

    async def unlock(self, version: uuid.UUID, password: str, who: Person) -> httpx.Response:
        return await self.net.call(
            "POST", f"/v1/evidence-versions/{version}/unlock", who, body={"password": password}
        )

    async def count(self, sql: str, *args: object) -> int:
        return int(str(await self.seed.value(sql, *args)))

    async def written_for(self, who: Person) -> tuple[int, int, int]:
        """What a reveal by `who` leaves: `pii_reveals` rows, `pii.revealed` audit events by
        them, and `pii.revealed` access events by them."""
        reveals = await self.count(
            "SELECT count(*) FROM pii_reveals WHERE user_id = $1", who.user_id
        )
        audits = await self.count(
            "SELECT count(*) FROM audit_events WHERE action = 'pii.revealed' AND actor_id = $1",
            str(who.user_id),
        )
        accessed = await self.count(
            "SELECT count(*) FROM access_events WHERE kind = 'pii.revealed' AND actor_id = $1",
            who.user_id,
        )
        return reveals, audits, accessed


@pytest.fixture
async def world(net: Net, seed: Seeder) -> World:
    tenant_id = await seed.firm()
    await _flags(seed, tenant_id)
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Ashford")
    samuel = await seed.person(tenant_id)
    rhea = await seed.person(tenant_id)
    await seed.member(site, samuel, "staff")
    await seed.member(site, rhea, "reviewer")
    client = await seed.client_contact(site, "client_admin")
    return World(net, tenant_id, owner, samuel, rhea, client, site)


def _corpus(name: str) -> bytes:
    return {doc.name: doc.content for doc in pii_corpus()}[name]


def _image(response: httpx.Response) -> Image.Image:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    image = Image.open(io.BytesIO(response.content))
    assert "A" not in image.getbands()  # no alpha: nothing shows through a mask
    return image.convert("RGB")


def _colours(image: Image.Image, rect: tuple[float, float, float, float], scale: float) -> int:
    """Distinct colours strictly inside `rect` (page points, top-left origin)."""
    x0, top, x1, bottom = (v * scale for v in rect)
    box = (int(x0) + 1, int(top) + 1, int(x1) - 1, int(bottom) - 1)
    assert box[2] > box[0] and box[3] > box[1], rect
    found = image.crop(box).getcolors(maxcolors=1 << 20)
    assert found is not None
    return len(found)


def _rect(mask: dict[str, object]) -> tuple[float, float, float, float]:
    x0, top, x1, bottom = (float(v) for v in cast(list[float], mask["rect"]))
    return x0, top, x1, bottom


def _assert_masked(image: Image.Image, manifest: dict[str, object]) -> None:
    pages = cast(list[dict[str, object]], manifest["pages"])
    geometry = pages[0]
    assert image.width == geometry["image_w"]
    scale = image.width / float(cast(float, geometry["width_pt"]))
    masks = cast(list[dict[str, object]], manifest["pii_masks"])
    assert masks, "the form has detected regions"
    for mask in masks:
        if mask["page"] != 1:
            continue
        assert _colours(image, _rect(mask), scale) == 1, mask["kind"]  # one flat colour
    assert _colours(image, LABEL_BOX, scale) > 1  # the label beside them still has ink


def _clear_of(text: str, *values: str) -> None:
    assert not has_tin(text), text
    for shape in TIN_SHAPES:
        assert not shape.search(text), (shape.pattern, text)
    for value in values:
        assert value not in text
        assert value.replace("-", "") not in text


# --- AC-23 (AC4.1): detection recall over the corpus ------------------------------------------


@pytest.mark.parametrize("name", CORPUS)
async def test_ac23_every_corpus_value_is_a_mask_in_the_manifest(world: World, name: str) -> None:
    """Recall 1.0 on the corpus (P-03-T13 acceptance), read from the manifest a viewer gets."""
    assert {
        (p, k, last4) for p, k, last4 in {d.name: d for d in pii_corpus()}[name].expected
    } == EXPECTED[name]  # the corpus still prints what these literals say
    upload = await world.upload(_corpus(name))
    manifest = await world.manifest(upload.version)
    assert manifest["status"] == "ready"
    masks = cast(list[dict[str, object]], manifest["pii_masks"])
    for page, kind, last4 in EXPECTED[name]:
        found = [m for m in masks if (m["page"], m["kind"]) == (page, kind)]
        if last4 is not None:
            found = [m for m in found if str(m["display"]).endswith(last4)]
        assert found, (name, kind, last4, [(m["kind"], m["display"]) for m in masks])
        if kind in TOKENS:
            expected = TOKENS[kind].format(last4=last4)
            assert [m["display"] for m in found] == [expected], (kind, found)
        else:  # a routing number: its last four and nothing more
            assert all(sum(c.isdigit() for c in str(m["display"])) == 4 for m in found)
    stored = await world.seed.rows(
        "SELECT kind, last4, value_sealed FROM pii_regions WHERE evidence_version_id = $1",
        upload.version,
    )
    held = {(r["kind"], r["last4"]) for r in stored}
    assert {(k, last4) for _, k, last4 in EXPECTED[name]} <= held
    assert all(r["value_sealed"] for r in stored)


async def test_ac23_the_unlabelled_number_that_fails_every_rule_is_not_masked(
    world: World,
) -> None:
    """P-03 §4.4: unlabelled matches need validity; `000-00-1111` (area 000) has none."""
    upload = await world.upload(_corpus("Direct deposit"))
    masks = await world.masks(upload.version)
    assert not [m for m in masks if "1111" in str(m["display"])]
    low, high = REFERENCE_BAND
    on_line = [m for m in masks if low <= (_rect(m)[1] + _rect(m)[3]) / 2 <= high]
    assert on_line == [], on_line
    last4s = await world.seed.rows(
        "SELECT last4 FROM pii_regions WHERE evidence_version_id = $1", upload.version
    )
    assert "1111" not in {r["last4"] for r in last4s}


# --- AC-24 (AC4.2): every page image served by every route is opaque in every region ----------


@pytest.mark.parametrize("name", CORPUS)
async def test_ac24_every_page_route_serves_opaque_pixels_in_every_region(
    world: World, name: str
) -> None:
    upload = await world.upload(_corpus(name))
    manifest = await world.manifest(upload.version)
    engagement = world.site.engagement_id
    routes = (
        f"/v1/evidence-versions/{upload.version}/pages/1",
        f"/v1/engagements/{engagement}/request-items/{upload.item}/uploads/{upload.version}"
        "/preview/pages/1",
        f"/v1/engagements/{engagement}/evidence-versions/{upload.version}/preview/pages/1",
    )
    for path in routes:
        response = await world.net.call("GET", path, world.samuel)
        _assert_masked(_image(response), manifest)


# --- AC-25, AC-40 (AC4.3, AC7.3): agent material is masked ------------------------------------


@pytest.mark.parametrize(
    ("form", "clear", "tokens"),
    [
        ("W-2", (W2_SSN, W2_EIN), ("•••-••-6081", "••-•••0287")),
        ("1099-INT", (F1099_SSN, F1099_EIN), ("•••-••-3456", "••-•••4321")),
    ],
)
async def test_ac25_upload_review_material_holds_only_mask_tokens(
    world: World, form: str, clear: tuple[str, ...], tokens: tuple[str, ...]
) -> None:
    upload = await world.upload(_corpus(form))
    material = await review_material(world.system, upload.version)
    assert material is not None
    texts = [*material.pages.values(), *(text for _, text in material.excerpt_pages)]
    assert texts
    whole = "\n".join(texts)
    _clear_of(whole, *clear)
    for token in tokens:
        assert token in whole, (token, whole)


async def test_ac40_matcher_material_for_an_inbox_1099_holds_only_mask_tokens(
    world: World,
) -> None:
    entry = await add_to_inbox(
        _person(world.samuel),
        world.site.engagement_id,
        file_name="consolidated-1099.pdf",
        content=form_1099_pdf(),
    )
    given = UploadInput(str(world.tenant_id), UPLOAD_INBOX, str(entry.id))
    await extract_upload(given)
    await words_upload(given)
    await pii_scan_upload(given)
    material = await match_material(world.system, entry.id)
    assert material is not None
    whole = "\n".join([*material.pages.values(), *(text for _, text in material.excerpt_pages)])
    assert whole
    _clear_of(whole, F1099_SSN, F1099_EIN)
    assert "•••-••-3456" in whole and "••-•••4321" in whole


# --- AC-26, AC-28 (AC4.4, AC4.6): the `pii.reveal` matrix row over HTTP -----------------------

ALLOWED: Final = ("engagement_partner", "manager", "senior", "staff", "eqr_reviewer")
REFUSED_403: Final = ("reviewer", "client_admin", "client_contributor", "offshore_staff")
# Roles the evidence read itself doesn't name: refused as forbidden or as never-existed.
REFUSED_EITHER: Final = ("client_service", "specialist")
NOT_ON_ENGAGEMENT: Final = ("member_elsewhere", "firm_admin", "practice_leader")


async def _as(world: World, role: str) -> Person:
    seed, site = world.seed, world.site
    if role in {"engagement_partner", "manager", "senior", "staff", "reviewer"}:
        who = await seed.person(world.tenant_id)
        await seed.member(site, who, cast(Role, role))
        return who
    if role in {"eqr_reviewer", "client_service", "specialist"}:
        return await _member(seed, site, role)
    if role in {"client_admin", "client_contributor"}:
        return await seed.client_contact(site, role)
    if role == "offshore_staff":
        who = await seed.person(world.tenant_id)
        await seed.member(site, who, "staff")
        await seed.run(
            "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
            world.tenant_id,
            who.user_id,
        )
        return who
    if role == "member_elsewhere":
        return await seed.person(world.tenant_id)
    return await seed.person(world.tenant_id, role)  # a firm role, on no engagement


@pytest.mark.parametrize("role", ALLOWED)  # eqr_reviewer reads evidence since DEC-427 (ED-106)
async def test_ac26_a_role_the_matrix_allows_reveals_the_1099_recipient_tin(
    world: World, role: str
) -> None:
    upload = await world.upload(form_1099_pdf())
    region = await world.mask_id(upload.version, "ssn")
    who = await _as(world, role)
    response = await world.reveal(upload.version, region, who)
    assert response.status_code == 201, response.text
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    assert (body["value"], body["kind"], body["mask_id"]) == (F1099_SSN, "ssn", region)
    assert await world.written_for(who) == (1, 1, 1)


@pytest.mark.parametrize("role", REFUSED_403 + REFUSED_EITHER + NOT_ON_ENGAGEMENT)
async def test_ac28_a_role_the_matrix_denies_is_refused_and_nothing_is_written(
    world: World, role: str
) -> None:
    upload = await world.upload(form_1099_pdf())
    region = await world.mask_id(upload.version, "ssn")
    who = await _as(world, role)
    response = await world.reveal(upload.version, region, who)
    if role in REFUSED_403:
        assert (response.status_code, response.json()) == (403, FORBIDDEN)
    elif role in NOT_ON_ENGAGEMENT:  # the version is invisible to them (DEC-43, DEC-370 order)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)
    else:
        assert (response.status_code, response.json()) in [(403, FORBIDDEN), (404, NOT_FOUND)]
    assert "3456" not in response.text and "900-12" not in response.text
    assert await world.written_for(who) == (0, 0, 0)
    assert (
        await world.count("SELECT count(*) FROM pii_reveals WHERE tenant_id = $1", world.tenant_id)
        == 0
    )


async def test_ac28_another_firm_reveals_nothing_and_reads_the_version_as_never_existed(
    world: World,
) -> None:
    upload = await world.upload(form_1099_pdf())
    region = await world.mask_id(upload.version, "ssn")
    elsewhere = await world.seed.firm()
    await _flags(world.seed, elsewhere)
    outsider = await world.seed.person(elsewhere, "firm_admin")
    response = await world.reveal(upload.version, region, outsider)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert await world.written_for(outsider) == (0, 0, 0)
    assert (
        await world.count(
            "SELECT count(*) FROM pii_reveals WHERE tenant_id = ANY($1::uuid[])",
            [world.tenant_id, elsewhere],
        )
        == 0
    )


async def test_ac28_the_manifest_offers_the_reveal_only_to_a_role_that_holds_it(
    world: World,
) -> None:
    upload = await world.upload(form_1099_pdf())
    staff = await world.manifest(upload.version)
    reviewer = await world.manifest(upload.version, world.rhea)
    assert "pii.reveal" in cast(list[str], staff["allowed_actions"])
    assert "pii.reveal" not in cast(list[str], reviewer["allowed_actions"])


# --- AC-27 (AC4.5; DEC-370): MFA for every kind ------------------------------------------------


async def test_ac27_a_bank_account_reveal_without_recent_mfa_asks_for_a_step_up(
    world: World,
) -> None:
    upload = await world.upload(form_1099_pdf())
    region = await world.mask_id(upload.version, "bank_account")
    stale = await world.reveal(upload.version, region, world.samuel, mfa=False)
    assert stale.status_code == 403, stale.text
    assert stale.json()["detail"] == "forbidden"
    assert stale.json()["facts"]["reason"] == "mfa_required"
    assert "4410" not in stale.text and "2291" not in stale.text
    assert await world.written_for(world.samuel) == (0, 0, 0)
    fresh = await world.reveal(upload.version, region, world.samuel)
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["kind"] == "bank_account"
    assert fresh.json()["value"].replace("-", "").endswith("44102291")


# --- AC-29 (AC4.7): the limit is per person ----------------------------------------------------


async def test_ac29_the_limit_is_per_person_and_its_refusal_writes_no_reveal(
    world: World,
) -> None:
    upload = await world.upload(form_1099_pdf())
    region = await world.mask_id(upload.version, "ssn")
    for _ in range(20):
        await world.seed.run(
            "INSERT INTO pii_reveals (tenant_id, region_id, evidence_version_id, user_id, "
            "actor_kind, expires_at) VALUES ($1, $2, $3, $4, 'human', "
            "clock_timestamp() + interval '30 seconds')",
            world.tenant_id,
            uuid.UUID(region),
            upload.version,
            world.samuel.user_id,
        )
    throttled = await world.reveal(upload.version, region, world.samuel)
    assert throttled.status_code == 429, throttled.text
    assert throttled.json()["detail"] == "reveal_rate_limited"
    assert throttled.headers["retry-after"] == str(throttled.json()["facts"]["retry_after"])
    assert F1099_SSN not in throttled.text
    assert await world.written_for(world.samuel) == (20, 0, 0)
    colleague = await _as(world, "staff")
    allowed = await world.reveal(upload.version, region, colleague)
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["value"] == F1099_SSN


# --- AC-26 (AC4.4; DEC-60): every sink of a reveal holds no value beyond the last four ---------


@pytest.mark.parametrize(
    ("make", "kind", "clear", "beyond_last4"),
    [
        (k1_pdf, "ein", K1_EIN, ("00-4567890", "004567890", "4567890", "00-456")),
        (form_1099_pdf, "ssn", F1099_SSN, ("900-12-3456", "900123456", "900-12", "90012")),
    ],
    ids=["k1-ein", "1099-recipient-ssn"],
)
async def test_ac26_the_audit_row_access_event_and_outbox_hold_no_value(
    world: World,
    make: Callable[[], bytes],
    kind: str,
    clear: str,
    beyond_last4: tuple[str, ...],
) -> None:
    upload = await world.upload(make())
    region = await world.mask_id(upload.version, kind)
    response = await world.reveal(upload.version, region, world.samuel)
    assert response.status_code == 201, response.text
    assert (response.json()["value"], response.json()["kind"]) == (clear, kind)
    audits = await world.seed.rows(
        "SELECT to_jsonb(a) AS doc, a.actor_kind, a.actor_id, a.target_id FROM audit_events a "
        "WHERE a.tenant_id = $1 AND a.action = 'pii.revealed'",
        world.tenant_id,
    )
    [audited] = audits
    assert (audited["actor_kind"], audited["actor_id"]) == ("human", str(world.samuel.user_id))
    assert audited["target_id"] == str(upload.version)
    accessed = await world.seed.rows(
        "SELECT to_jsonb(e) AS doc, e.subject_type, e.subject_id FROM access_events e "
        "WHERE e.tenant_id = $1 AND e.kind = 'pii.revealed'",
        world.tenant_id,
    )
    assert [(a["subject_type"], str(a["subject_id"])) for a in accessed] == [
        ("pii_region", region)
    ]
    reveals = await world.seed.rows(
        "SELECT to_jsonb(r) AS doc FROM pii_reveals r WHERE r.tenant_id = $1", world.tenant_id
    )
    outbox = await world.seed.rows(
        "SELECT to_jsonb(o) AS doc FROM outbox o WHERE o.tenant_id = $1", world.tenant_id
    )
    every_audit = await world.seed.rows(
        "SELECT to_jsonb(a) AS doc FROM audit_events a WHERE a.tenant_id = $1", world.tenant_id
    )
    assert len(reveals) == 1
    assert not [o for o in outbox if "pii." in str(o["doc"])]  # never fanned out
    for sink in (audits, accessed, reveals, outbox, every_audit):
        dumped = json.dumps([str(r["doc"]) for r in sink])
        for piece in beyond_last4:
            assert piece not in dumped, piece


# --- AC-31 to AC-35 (F5; C4 §3.5, §6; DEC-425): unlock a password PDF -------------------------


async def _content(world: World, version: uuid.UUID) -> bytes:
    response = await world.net.call(
        "GET",
        f"/v1/engagements/{world.site.engagement_id}/evidence-versions/{version}/content",
        world.samuel,
    )
    assert response.status_code == 200, response.text
    return response.content


async def _fingerprint(world: World, version: uuid.UUID) -> object:
    return await world.seed.value(
        "SELECT fingerprint FROM evidence_versions WHERE id = $1", version
    )


async def _unlock_audits(world: World) -> list[str]:
    rows = await world.seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 "
        "AND action LIKE 'evidence_version.unlock%' ORDER BY seq",
        world.tenant_id,
    )
    return [str(r["action"]) for r in rows]


async def test_ac31_a_password_pdf_reads_password_protected_and_offers_unlock(
    world: World,
) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    staff = await world.manifest(upload.version)
    assert staff["status"] == "password_protected"
    assert staff["pii_masks"] == [] and staff["derivation_id"] is None
    assert "evidence.unlock" in cast(list[str], staff["allowed_actions"])
    reviewer = await world.manifest(upload.version, world.rhea)
    assert "evidence.unlock" not in cast(list[str], reviewer["allowed_actions"])


async def test_ac33_a_wrong_password_answers_wrong_password_with_fewer_attempts_left(
    world: World,
) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    first = await world.unlock(upload.version, NOT_IT, world.samuel)
    assert first.status_code == 200, first.text
    assert "no-store" in first.headers["cache-control"]
    assert (first.json()["status"], first.json()["attempts_left"]) == ("wrong_password", 4)
    assert first.json()["derivation_id"] is None
    second = await world.unlock(upload.version, NOT_IT, world.samuel)
    assert (second.json()["status"], second.json()["attempts_left"]) == ("wrong_password", 3)
    assert NOT_IT not in first.text + second.text
    assert await _unlock_audits(world) == ["evidence_version.unlock_failed"] * 2
    assert (await world.manifest(upload.version))["status"] == "password_protected"


async def test_ac32_the_right_password_derives_masked_pages_and_leaves_the_evidence_unchanged(
    world: World,
) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    before = await _content(world, upload.version)
    fingerprint = await _fingerprint(world, upload.version)
    assert before == upload.content
    response = await world.unlock(upload.version, OPENS_WITH, world.samuel)
    assert response.status_code == 200, response.text
    assert "no-store" in response.headers["cache-control"]
    body = response.json()
    assert (body["status"], body["attempts_left"]) == ("ready", None)
    derivation = body["derivation_id"]
    assert derivation is not None
    assert OPENS_WITH not in response.text
    manifest = await world.manifest(upload.version)
    assert (manifest["status"], manifest["derivation_id"]) == ("ready", derivation)
    masks = cast(list[dict[str, object]], manifest["pii_masks"])
    shown = {(m["kind"], m["display"]) for m in masks}
    assert ("ssn", "•••-••-3456") in shown and ("ein", "••-•••4321") in shown
    assert "evidence.unlock" not in cast(list[str], manifest["allowed_actions"])
    page = await world.net.call(
        "GET", f"/v1/evidence-versions/{upload.version}/pages/1", world.samuel
    )
    _assert_masked(_image(page), manifest)
    assert await _content(world, upload.version) == before  # the evidence is unchanged
    assert await _fingerprint(world, upload.version) == fingerprint
    assert await _unlock_audits(world) == ["evidence_version.unlocked"]
    published = await world.count(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'evidence_version.unlocked'",
        world.tenant_id,
    )
    assert published == 1
    sinks = await world.seed.rows(
        "SELECT to_jsonb(a) AS doc FROM audit_events a WHERE a.tenant_id = $1", world.tenant_id
    )
    assert OPENS_WITH not in json.dumps([str(r["doc"]) for r in sinks])


async def test_ac32_a_value_on_the_unlocked_derivation_reveals_as_printed(world: World) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    unlocked = await world.unlock(upload.version, OPENS_WITH, world.samuel)
    assert unlocked.json()["status"] == "ready", unlocked.text
    region = await world.mask_id(upload.version, "ssn")
    response = await world.reveal(upload.version, region, world.samuel)
    assert response.status_code == 201, response.text
    assert (response.json()["value"], response.json()["kind"]) == (F1099_SSN, "ssn")


async def test_ac32_an_unlocked_or_plain_version_answers_not_password_protected(
    world: World,
) -> None:
    locked = await world.upload(password_pdf(OPENS_WITH))
    plain = await world.upload(w2_pdf())
    first = await world.unlock(locked.version, OPENS_WITH, world.samuel)
    assert first.json()["status"] == "ready", first.text
    again = await world.unlock(locked.version, OPENS_WITH, world.samuel)
    assert (again.status_code, again.json()) == (409, {"detail": "not_password_protected"})
    never = await world.unlock(plain.version, OPENS_WITH, world.samuel)
    assert (never.status_code, never.json()) == (409, {"detail": "not_password_protected"})
    assert (
        await world.count(
            "SELECT count(*) FROM evidence_derivations WHERE tenant_id = $1", world.tenant_id
        )
        == 1
    )


@pytest.mark.parametrize(
    "role", ["client_admin", "client_contributor", "reviewer", "eqr_reviewer"]
)
async def test_ac35_unlock_is_refused_to_a_client_and_to_roles_without_it(
    world: World, role: str
) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    who = await _as(world, role)
    response = await world.unlock(upload.version, OPENS_WITH, who)
    # Every one of them sees the version (eqr_reviewer since DEC-427) and lacks the action.
    assert (response.status_code, response.json()) == (403, FORBIDDEN)
    assert OPENS_WITH not in response.text
    assert await _unlock_audits(world) == []
    assert (
        await world.count(
            "SELECT count(*) FROM evidence_derivations WHERE tenant_id = $1", world.tenant_id
        )
        == 0
    )
    assert (await world.manifest(upload.version))["status"] == "password_protected"


async def test_ac35_another_firm_unlocks_nothing(world: World) -> None:
    upload = await world.upload(password_pdf(OPENS_WITH))
    elsewhere = await world.seed.firm()
    await _flags(world.seed, elsewhere)
    outsider = await world.seed.person(elsewhere, "firm_admin")
    response = await world.unlock(upload.version, OPENS_WITH, outsider)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert await _unlock_audits(world) == []
    assert (
        await world.count(
            "SELECT count(*) FROM evidence_derivations WHERE tenant_id = $1", world.tenant_id
        )
        == 0
    )
