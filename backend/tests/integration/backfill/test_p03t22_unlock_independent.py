# ac-test-author: ayushkbhatia
"""SPEC-322 AC-31 to AC-35 (P-03-T22, TASK-1436): a password-protected PDF is unlocked into
derived records without changing the evidence, and the password a person types is found nowhere
outside the request.

A planted sentinel password (and a second, wrong, sentinel) is looked for in every sink the spec
names (AC-34): the product's log records and the process's own stdout and stderr (the isolated
child's included), every row of every table in the database, every object version in the evidence
bucket, every outbox payload and every workflow start or signal handed to Temporal (the relay
delivering the unlock's events through the worker's own subscribers), and every event error
tracking would send when an unlock fails part-way. It is never echoed in a response. The version's
row, its stored object and the bytes the content route serves are identical before and after the
unlock, and the derived pages, scan run, regions and masked rendition all name one
`evidence_derivations` row (AC-32). Five wrong passwords by one person on one version in fifteen
minutes and the sixth attempt is 429 `unlock_rate_limited` (AC-33). An agent, a client principal
and a role without `evidence.unlock` are refused; a wall and another firm read as never-existed
(AC-35, DEC-43).

Boundary: `create_app()` over HTTP on the migrated Postgres and the compose S3 image, as the
firm's people and the client's. Uploads go through the client upload route and the rendition
steps a v7 run calls. The worker's relay is replaced by delivering the outbox rows to
`abacus.worker.__main__.publisher()` with a recording Temporal client; error tracking runs with an
in-memory transport through `configure_error_tracking`, as the API process starts it.

Later decisions and contract lines followed instead of the spec's words: C4 §5 (a wrong password
is 200 `{status: wrong_password, attempts_left}`, not an error), C4 §3.5 and DEC-425 (a second
unlock of a derived version answers 409 `not_password_protected`; 429 facts carry `limit` and
`retry_after`; refusals other than `mfa_required` are the plain `{"detail": "forbidden"}`,
DEC-370).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Final, cast

import asyncpg
import httpx
import pytest
import sentry_sdk
import yaml
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.error_tracking import configure_error_tracking
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import configure_temporal_client
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_VERSION, UploadInput, check_upload_content
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.masked_previews import masked_preview_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.words import words_upload
from abacus_tools.synthetic.documents import password_pdf, w2_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "task1436-unlock-sentinel"
MASTER: Final = b"task1436-unlock-sentinel-master-key-0123456"
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
# The SHL-08d file's recipient TIN (a 9xx fake) printed under its label.
TIN_LAST4: Final = "3456"
DSN: Final = "https://public@example.invalid/1"
REPO: Final = Path(__file__).resolve().parents[4]
DERIVED: Final = ("evidence_pages", "pii_scan_runs", "pii_regions", "upload_previews")


def _sentinel(tag: str) -> str:
    """A password no fixture, seed or log line could hold by chance. 24 characters: inside the
    32 bytes a standard-security PDF password keeps, so the whole sentinel is the password."""
    return f"Snt{tag}{uuid.uuid4().hex[:20]}"[:24]


# --- sinks ------------------------------------------------------------------------------------


@dataclass
class Recorder:
    """Stands in for the Temporal client: every method call, with its arguments, is recorded."""

    calls: list[str] = field(default_factory=list[str])

    def __getattr__(self, name: str) -> Callable[..., Awaitable[None]]:
        async def call(*args: object, **kwargs: object) -> None:
            self.calls.append(f"{name} {args!r} {kwargs!r}")

        return call


class Capture(Transport):
    events: ClassVar[list[dict[str, Any]]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            Capture.events.append(cast(dict[str, Any], event))
        for item in envelope.items:  # anything else the client would send
            payload = item.get_bytes()
            Capture.events.append({"raw": payload.decode("utf-8", "replace")})


def _hex(value: str) -> str:
    return value.encode().hex()


def _in(text: str, *secrets: str) -> list[str]:
    """Which of `secrets` appear in `text`, as typed or hex-encoded (how a bytea renders)."""
    lowered = text.lower()
    return [s for s in secrets if s in text or _hex(s) in lowered]


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
def wired(raw: S3Client) -> Iterator[Recorder]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    recorder = Recorder()
    configure_temporal_client(cast(Any, recorder))
    forget_flags()
    yield recorder
    forget_flags()
    configure_temporal_client(None)
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
def temporal(wired: Recorder) -> Recorder:
    return wired


async def _rendered(given: UploadInput) -> None:
    """The steps a v7 upload run takes: extract, check, words, PII scan, masked page."""
    await extract_upload(given)
    await check_upload_content(given)
    await words_upload(given)
    await pii_scan_upload(given)
    await masked_preview_upload(given)


@dataclass(frozen=True)
class World:
    net: Net
    tenant_id: uuid.UUID
    owner: Person
    samuel: Person  # onshore staff: holds evidence.unlock
    hana: Person  # onshore manager: holds evidence.unlock
    rhea: Person  # reviewer: no evidence.unlock
    lena: Person  # staff, walled from the client
    client: Person  # the client's admin
    site: Site
    locked: uuid.UUID  # the Halvard 1099, uploaded locked with `password`
    password: str
    original: bytes

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def unlock_path(self) -> str:
        return f"/v1/evidence-versions/{self.locked}/unlock"

    async def upload(self, content: bytes) -> uuid.UUID:
        item = await self.seed.item(self.site, f"Document {uuid.uuid4().hex[:6]}")
        response = await self.net.http.post(
            f"/v1/engagements/{self.site.engagement_id}/request-items/{item}/uploads",
            params={"filename": "Halvard_2025_Consolidated_1099.pdf"},
            content=content,
            headers={**self.net.headers(self.client), "Content-Type": PDF},
        )
        assert response.status_code == 201, response.text
        version = uuid.UUID(response.json()["evidence_version_id"])
        await _rendered(UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(version)))
        return version

    async def unlock(self, password: str, who: Person | None = None) -> httpx.Response:
        return await self.net.call(
            "POST", self.unlock_path, who or self.samuel, body={"password": password}
        )

    async def manifest(self, who: Person | None = None) -> httpx.Response:
        return await self.net.call(
            "GET", f"/v1/evidence-versions/{self.locked}/viewer", who or self.samuel
        )

    async def content(self) -> bytes:
        response = await self.net.call(
            "GET",
            f"/v1/engagements/{self.site.engagement_id}/evidence-versions/{self.locked}/content",
            self.samuel,
        )
        assert response.status_code == 200, response.text
        return response.content

    async def version_row(self) -> dict[str, object]:
        [row] = await self.seed.rows(
            "SELECT fingerprint, storage_key, storage_version_id, size_bytes, media_type "
            "FROM evidence_versions WHERE id = $1",
            self.locked,
        )
        return dict(row)

    def stored(self) -> list[tuple[str, str, str]]:
        """The original's object versions in the bucket: key, version id, ETag."""
        key = f"tenants/{self.tenant_id}/"
        listed = storage_client().list_object_versions(Bucket=BUCKET, Prefix=key)
        return sorted(
            (v.get("Key", ""), v.get("VersionId", ""), v.get("ETag", ""))
            for v in listed.get("Versions", [])
        )

    async def audit(self, action: str) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT to_jsonb(a) AS doc FROM audit_events a "
            "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant_id,
            action,
        )
        return [_doc(r["doc"]) for r in rows]


_RAW: dict[str, S3Client] = {}


def storage_client() -> S3Client:
    return _RAW["client"]


def _doc(value: object) -> dict[str, object]:
    return json.loads(value) if isinstance(value, str) else dict(cast(dict[str, object], value))


async def _member(seed: Seeder, site: Site, role: str) -> Person:
    who = await seed.person(site.tenant_id)
    await seed.member(site, who, cast(Any, role))
    return who


@pytest.fixture
async def world(net: Net, seed: Seeder, raw: S3Client) -> World:
    _RAW["client"] = raw
    tenant_id = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1436')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Halvard")
    samuel = await _member(seed, site, "staff")
    hana = await _member(seed, site, "manager")
    rhea = await _member(seed, site, "reviewer")
    lena = await _member(seed, site, "staff")
    client = await seed.client_contact(site, "client_admin")
    password = _sentinel("R")
    original = password_pdf(password)
    shell = World(
        net, tenant_id, owner, samuel, hana, rhea, lena, client, site, uuid.uuid4(), "", b""
    )
    locked = await shell.upload(original)
    await net.wall(owner, lena, site)
    return dataclasses.replace(shell, locked=locked, password=password, original=original)


# --- AC-31: the locked state ------------------------------------------------------------------


async def test_ac31_a_locked_pdf_reads_password_protected_and_offers_unlock(world: World) -> None:
    manifest = await world.manifest()
    assert manifest.status_code == 200, manifest.text
    body = manifest.json()
    assert body["status"] == "password_protected"
    assert "evidence.unlock" in body["allowed_actions"]
    assert body.get("derivation_id") is None
    assert world.password not in manifest.text


async def test_ac31_the_reviewer_is_not_offered_unlock(world: World) -> None:
    manifest = await world.manifest(world.rhea)
    assert manifest.status_code == 200, manifest.text
    assert "evidence.unlock" not in manifest.json()["allowed_actions"]


# --- AC-32: a derivation, never a change to the evidence ---------------------------------------


async def test_ac32_the_right_password_derives_linked_masked_records(world: World) -> None:
    response = await world.unlock(world.password)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert body["attempts_left"] is None
    derivation = uuid.UUID(body["derivation_id"])
    assert "no-store" in response.headers.get("cache-control", "")

    linked = await world.seed.rows(
        "SELECT id, evidence_version_id FROM evidence_derivations WHERE id = $1", derivation
    )
    assert [r["evidence_version_id"] for r in linked] == [world.locked]
    for table in DERIVED:
        count = await world.seed.value(
            f"SELECT count(*) FROM {table} WHERE evidence_version_id = $1 "  # noqa: S608 -- fixed names
            "AND derivation_id = $2",
            world.locked,
            derivation,
        )
        assert int(str(count)) >= 1, table
        stray = await world.seed.value(
            f"SELECT count(*) FROM {table} WHERE evidence_version_id = $1 "  # noqa: S608 -- fixed names
            "AND derivation_id IS DISTINCT FROM $2 AND derivation_id IS NOT NULL",
            world.locked,
            derivation,
        )
        assert int(str(stray)) == 0, table
    regions = await world.seed.rows(
        "SELECT last4 FROM pii_regions WHERE derivation_id = $1", derivation
    )
    assert TIN_LAST4 in {r["last4"] for r in regions}  # the recipient's TIN was found and sealed

    manifest = await world.manifest()
    assert manifest.json()["status"] == "ready"
    assert manifest.json()["derivation_id"] == str(derivation)
    page = await world.net.call(
        "GET", f"/v1/evidence-versions/{world.locked}/pages/1", world.samuel
    )
    assert page.status_code == 200, page.text
    assert page.headers["content-type"].startswith("image/png")


async def test_ac32_the_version_bytes_and_fingerprint_are_unchanged(world: World) -> None:
    row_before = await world.version_row()
    objects_before = world.stored()
    served_before = await world.content()
    assert served_before == world.original
    assert row_before["fingerprint"] == hashlib.sha256(world.original).hexdigest()

    response = await world.unlock(world.password)
    assert response.json()["status"] == "ready", response.text

    assert await world.version_row() == row_before
    original_key = cast(str, row_before["storage_key"])
    assert [o for o in world.stored() if o[0] == original_key] == [
        o for o in objects_before if o[0] == original_key
    ]
    assert await world.content() == served_before == world.original
    versions = await world.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE evidence_item_id = "
        "(SELECT evidence_item_id FROM evidence_versions WHERE id = $1)",
        world.locked,
    )
    assert int(str(versions)) == 1  # a derivation, not a new version


async def test_ac32_the_unlock_is_audited_and_published(world: World) -> None:
    response = await world.unlock(world.password)
    derivation = response.json()["derivation_id"]
    [audited] = await world.audit("evidence_version.unlocked")
    assert audited["actor_kind"] == "human"
    assert str(world.samuel.user_id) in json.dumps(audited, default=str)
    events = await world.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'evidence_version.unlocked'",
        world.tenant_id,
    )
    assert len(events) == 1
    payload = json.dumps(_doc(events[0]["payload"]), default=str)
    assert str(world.locked) in payload and derivation in payload


async def test_ac32_a_second_unlock_answers_not_password_protected(world: World) -> None:
    assert (await world.unlock(world.password)).json()["status"] == "ready"
    again = await world.unlock(world.password)
    assert (again.status_code, again.json()["detail"]) == (409, "not_password_protected")
    assert world.password not in again.text
    derivations = await world.seed.value(
        "SELECT count(*) FROM evidence_derivations WHERE evidence_version_id = $1", world.locked
    )
    assert int(str(derivations)) == 1


async def test_ac32_an_unlocked_file_answers_not_password_protected(world: World) -> None:
    plain = await world.upload(w2_pdf())
    response = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{plain}/unlock",
        world.samuel,
        body={"password": world.password},
    )
    assert (response.status_code, response.json()["detail"]) == (409, "not_password_protected")
    assert world.password not in response.text


# --- AC-33: wrong passwords and the limit -------------------------------------------------------


async def test_ac33_a_wrong_password_returns_attempts_left_and_is_audited_by_count(
    world: World,
) -> None:
    wrong = _sentinel("W")
    response = await world.unlock(wrong)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "wrong_password",
        "attempts_left": 4,
        "derivation_id": None,
    }
    assert wrong not in response.text
    [failed] = await world.audit("evidence_version.unlock_failed")
    assert _in(json.dumps(failed, default=str), wrong, world.password) == []
    derivations = await world.seed.value(
        "SELECT count(*) FROM evidence_derivations WHERE evidence_version_id = $1", world.locked
    )
    assert int(str(derivations)) == 0
    assert (await world.manifest()).json()["status"] == "password_protected"


async def test_ac33_the_sixth_attempt_in_fifteen_minutes_is_rate_limited(world: World) -> None:
    wrong = _sentinel("W")
    left = [(await world.unlock(wrong)).json()["attempts_left"] for _ in range(5)]
    assert left == [4, 3, 2, 1, 0]
    throttled = await world.unlock(world.password)  # even the right one, inside the window
    assert throttled.status_code == 429, throttled.text
    body = throttled.json()
    assert body["detail"] == "unlock_rate_limited"
    assert body["facts"]["limit"] == 5 and body["facts"]["retry_after"] > 0
    assert _in(throttled.text, wrong, world.password) == []
    assert len(await world.audit("evidence_version.unlock_failed")) == 5
    assert len(await world.audit("evidence_version.unlock_throttled")) == 1
    assert await world.audit("evidence_version.unlocked") == []


async def test_ac33_the_limit_is_per_person_on_the_version(world: World) -> None:
    wrong = _sentinel("W")
    for _ in range(5):
        await world.unlock(wrong)
    response = await world.unlock(world.password, world.hana)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready"


# --- AC-35: who may unlock -----------------------------------------------------------------------


@pytest.mark.parametrize("who", ["client", "rhea"])
async def test_ac35_a_client_principal_and_a_role_without_unlock_are_refused(
    world: World, who: str
) -> None:
    person = cast(Person, getattr(world, who))
    response = await world.unlock(world.password, person)
    assert (response.status_code, response.json()) == (403, FORBIDDEN)
    assert world.password not in response.text
    assert await world.audit("evidence_version.unlocked") == []
    assert (await world.manifest()).json()["status"] == "password_protected"


async def test_ac35_an_agent_or_system_principal_is_refused_by_the_matrix_and_the_database(
    world: World,
) -> None:
    """INV-1 (C4 §5): an agent reaches HTTP only with a proven run's context, which this
    boundary cannot make, so the refusal is proven at the two layers a test can reach: the matrix
    denies `evidence.unlock` to agent, system and client roles, and the database holds no
    derivation without the person who unlocked it (`created_by_user_id` NOT NULL)."""
    matrix = REPO / "docs/architecture/permission-matrix"
    rows: dict[str, dict[str, object]] = {}
    for path in matrix.glob("*.yaml"):
        loaded = cast(dict[str, Any], yaml.safe_load(path.read_text()) or {})
        rows.update(cast(dict[str, dict[str, object]], loaded.get("actions", {}) or {}))
    unlock = rows["evidence.unlock"]
    for principal in ("agent", "system", "client_admin", "client_contributor", "client_viewer"):
        assert unlock.get(principal, "deny") == "deny", principal
    assert {r for r, v in unlock.items() if v == "allow"} == {
        "engagement_partner",
        "manager",
        "senior",
        "staff",
    }
    assert unlock.get("independence") == "required"
    with pytest.raises(asyncpg.NotNullViolationError):
        await world.seed.run(
            "INSERT INTO evidence_derivations (tenant_id, evidence_version_id, kind, "
            "created_by_user_id, extractor_version, renderer_version, detector_version) "
            "VALUES ($1, $2, 'password_unlock', NULL, 'x', 'x', 'x')",
            world.tenant_id,
            world.locked,
        )


async def test_ac35_a_wall_and_another_firm_read_as_never_existed(world: World) -> None:
    walled = await world.unlock(world.password, world.lena)
    assert (walled.status_code, walled.json()) == (404, NOT_FOUND)
    elsewhere = await world.seed.firm()
    for flag in FLAGS:
        await world.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1436')",
            elsewhere,
            flag,
        )
    outsider = await world.seed.person(elsewhere, "firm_admin")
    foreign = await world.unlock(world.password, outsider)
    assert (foreign.status_code, foreign.json()) == (404, NOT_FOUND)
    assert world.password not in walled.text + foreign.text
    assert await world.audit("evidence_version.unlock_failed") == []


async def test_ac35_the_route_is_absent_with_its_flag_off(world: World) -> None:
    await world.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'evidence.viewer_unlock'",
        world.tenant_id,
    )
    forget_flags()
    response = await world.unlock(world.password)
    assert response.status_code == 404, response.text
    assert await world.audit("evidence_version.unlocked") == []


# --- AC-34: the sentinel is found nowhere outside the request -----------------------------------


async def _every_row_holding(seed: Seeder, *secrets: str) -> list[str]:
    """`schema.table` for every table with a row whose text (bytea as hex) holds a secret."""
    tables = await seed.rows(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN "
        "('pg_catalog', 'information_schema') AND table_schema NOT LIKE 'pg_%'"
    )
    found: list[str] = []
    for t in tables:
        name = f'"{t["table_schema"]}"."{t["table_name"]}"'
        for secret in secrets:
            hit = await seed.value(
                f"SELECT EXISTS (SELECT 1 FROM {name} t WHERE t::text LIKE $1 "  # noqa: S608 -- catalogue names
                "OR lower(t::text) LIKE $2)",
                f"%{secret}%",
                f"%{_hex(secret)}%",
            )
            if hit:
                found.append(name)
    return found


async def test_ac34_the_sentinel_is_in_no_log_table_object_outbox_or_workflow(
    world: World,
    temporal: Recorder,
    caplog: pytest.LogCaptureFixture,
    capfd: pytest.CaptureFixture[str],
) -> None:
    caplog.set_level(logging.DEBUG)
    wrong = _sentinel("W")
    mark = await world.seed.value("SELECT coalesce(max(seq), 0) FROM outbox")
    responses = [await world.unlock(wrong), await world.unlock(world.password)]
    assert [r.json()["status"] for r in responses] == ["wrong_password", "ready"]

    # Never echoed back.
    for response in responses:
        assert _in(response.text + str(response.headers), wrong, world.password) == []

    # The relay delivers what the unlock emitted to the worker's subscribers (Temporal's input).
    from abacus.worker.__main__ import publisher

    emitted = await world.seed.rows(
        "SELECT id, tenant_id, event_type, payload FROM outbox WHERE seq > $1 ORDER BY seq",
        mark,
    )
    assert any(e["event_type"] == "evidence_version.unlocked" for e in emitted)
    route = publisher()
    for e in emitted:
        if e["tenant_id"] != world.tenant_id:
            continue  # another test's event, concurrently
        await route.publish(
            OutboxEvent(e["id"], e["tenant_id"], e["event_type"], _doc(e["payload"]))
        )
        assert _in(json.dumps(_doc(e["payload"]), default=str), wrong, world.password) == []
    assert _in("\n".join(temporal.calls), wrong, world.password) == []

    # Logs: every record any logger wrote, with its extras, and the process's own output
    # (the isolated child inherits the descriptors).
    records = "\n".join(f"{r.getMessage()} {r.__dict__!r}" for r in caplog.records)
    assert _in(records, wrong, world.password) == []
    out, err = capfd.readouterr()
    assert _in(out + err, wrong, world.password) == []

    # The database: every row of every table.
    assert await _every_row_holding(world.seed, wrong, world.password) == []

    # Storage: every object version in the bucket, as stored.
    client = storage_client()
    listed = client.list_object_versions(Bucket=BUCKET, Prefix=f"tenants/{world.tenant_id}/")
    versions = listed.get("Versions", [])
    assert versions  # the original and the derived pages
    for v in versions:
        body = client.get_object(
            Bucket=BUCKET, Key=v.get("Key", ""), VersionId=v.get("VersionId", "")
        )
        data = body["Body"].read()
        for secret in (wrong, world.password):
            assert secret.encode() not in data, v.get("Key")
            assert secret.encode("utf-16-le") not in data, v.get("Key")


class _NoWrites:
    """The bucket for one call: reads pass through, every write fails, as a storage outage would
    part-way through the unlock (after the file is opened)."""

    def __init__(self, inner: S3Client) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        if name.startswith("put_"):

            def refused(*_args: object, **_kwargs: object) -> None:
                raise RuntimeError("storage unavailable")

            return refused
        return getattr(self._inner, name)


@pytest.fixture
def tracked(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    monkeypatch.setenv("ABACUS_SENTRY_DSN", DSN)
    settings.cache_clear()
    monkeypatch.setattr("abacus.kernel.error_tracking._configured", False)
    real = sentry_sdk.init

    def init(**options: object) -> None:
        real(**cast(dict[str, Any], options), transport=Capture)

    monkeypatch.setattr(sentry_sdk, "init", init)
    Capture.events = []
    assert configure_error_tracking("abacus-api") is True
    yield Capture.events
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    monkeypatch.setattr("abacus.kernel.error_tracking._configured", False)


async def test_ac34_an_unlock_that_fails_part_way_sends_no_sentinel_to_error_tracking(
    world: World, raw: S3Client, tracked: list[dict[str, Any]]
) -> None:
    storage.reset_storage()
    storage.configure_storage(cast(S3Client, _NoWrites(raw)), BUCKET)
    try:
        response = await world.unlock(world.password)
    finally:
        storage.reset_storage()
        storage.configure_storage(raw, BUCKET)
    assert response.status_code == 500, response.text
    assert world.password not in response.text
    sentry_sdk.flush(2.0)
    assert tracked, "the unexpected error was reported"
    sent = json.dumps(tracked, default=str)
    assert _in(sent, world.password) == []
    # Nothing was derived, and the file still opens with the right password afterwards.
    derivations = await world.seed.value(
        "SELECT count(*) FROM evidence_derivations WHERE evidence_version_id = $1", world.locked
    )
    assert int(str(derivations)) == 0
    assert (await world.unlock(world.password)).json()["status"] == "ready"


async def test_ac34_the_password_field_is_bounded_and_never_echoed_in_a_validation_error(
    world: World,
) -> None:
    long = _sentinel("L") * 11  # 264 characters: over the contract's 256
    response = await world.unlock(long)
    assert response.status_code == 422, response.text
    assert long[:24] not in response.text
    extra = await world.net.call(
        "POST",
        world.unlock_path,
        world.samuel,
        body={"password": world.password, "remember": True},
    )
    assert extra.status_code == 422, extra.text
    assert world.password not in extra.text


async def test_inv_no_table_the_unlock_writes_has_a_password_column(world: World) -> None:
    """No table the unlock writes has a column a password could be stored in (C4 §3.5)."""
    rows = await world.seed.rows(
        "SELECT table_name || '.' || column_name AS c FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = ANY($1::text[]) "
        "AND (column_name ILIKE '%password%' OR column_name ILIKE '%secret%')",
        ["evidence_derivations", *DERIVED],
    )
    assert [r["c"] for r in rows] == []
