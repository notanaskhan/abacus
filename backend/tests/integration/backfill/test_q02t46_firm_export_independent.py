# ac-test-author: ayushkbhatia
"""Q-02-T46 (TASK-1455): independent AC tests (ADR-078) for the firm export, Q-02 AC-40 and AC-41
(SPEC-341 story 10; DEC-72, conflict C-11), and the manifest case Q-02-T47 must pass unedited.

Dual approval: the security admin requests naming an approver; the requester approving is 409
`approver_must_differ`, naming oneself is 422 `approver_invalid`, and the database refuses one
person as both halves even with triggers off; the named approver, with a fresh second factor,
starts the build, which stores the archive sealed under the tenant's key with a SHA-256
manifest. Links: the link lives 15 minutes, can be minted for 7 days from approval, opens only
for the person it was issued to (the requester or the approver), needs a fresh second factor, and
answers 410 after either window. Manifest: `manifest_sha256` is the digest of `manifest.json`,
which lists every other file of the archive with its bytes and SHA-256; with Q-02-T47 the index
holds one package per engagement.

Boundary: `create_app()` over HTTP for every `/v1/firm/data-exports` route and the link's own
path; `evidence.api.FirmExportWorkflow` run by a Temporal dev-server worker with the evidence
activities (the outbox relay that starts it in production does not run here, so the test starts
it by its contract id after the approval); the business clock frozen past each window; storage,
audit and access rows read as the superuser. Expectations: SPEC-341 AC-40/AC-41,
`docs/contracts/compliance-kernel.md` v1.3 §2 to §7, DEC-508 (the v1 archive is an index and a
manifest), DEC-509 (a link is the archive route's path for one signed-in person, not a presigned
URL: it supersedes the row's "15-minute presigned links"), DEC-511. The contract's 403 with
`facts.reason = mfa_required` is followed for a stale factor (it supersedes AC-2's 401 wording
for these routes). Probes return what they found wrong; `test_seeded_*` plant violations.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import asyncpg
import httpx
import pytest
from temporalio.client import Client
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.dispatch import queue_for
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import data_converter
from abacus.modules.evidence import export_storage
from abacus.modules.evidence.api import ACTIVITIES as EVIDENCE_ACTIVITIES
from abacus.modules.evidence.api import FirmExportInput, FirmExportWorkflow

from .support import Net, Person, Seeder

Json = dict[str, object]
EXPORTS: Final = "/v1/firm/data-exports"
ARCHIVES: Final = "q02t46-exports"
MASTER: Final = b"q02t46-independent-master-key-0123456789"
LINK_LIFE: Final = timedelta(minutes=15)
WINDOW: Final = timedelta(days=7)
ZIP_MAGIC: Final = b"PK\x03\x04"


# --- wiring: the exports store, the tenant key, Temporal -----------------------------------------


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=ARCHIVES, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", f"q02t46-{uuid.uuid4().hex[:8]}")
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    export_storage.configure_exports(raw, ARCHIVES)
    yield
    export_storage.reset_exports()
    reset_key_service()
    forget_flags()


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    activities = cast("list[Callable[..., object]]", list(EVIDENCE_ACTIVITIES))
    async with Worker(
        client,
        task_queue=queue_for("batch"),
        workflows=[FirmExportWorkflow],
        activities=activities,
    ):
        yield client


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    felix: Person  # security admin, the requester (the QI)
    margaret: Person  # partner level, the named approver
    second_admin: Person  # another security admin, neither half
    staff: Person
    engagements: tuple[uuid.UUID, ...]


async def _partner(seed: Seeder, tenant: uuid.UUID) -> Person:
    who = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
    )
    return who


async def _firm(net: Net, *, flag: bool = True) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    if flag:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'compliance.firm_export', 'true', 'test-seed', 'Q-02-T46')",
            tenant,
        )
    felix = await seed.person(tenant, "security_admin")
    margaret = await _partner(seed, tenant)
    second = await seed.person(tenant, "security_admin")
    staff = await seed.person(tenant)
    sites = [await seed.site(tenant, felix.user_id, f"q02t46-{n}") for n in range(2)]
    # ED-290 (DEC-640): the archive packages each engagement as the approver may read it, so the
    # named partner is on both engagements, as a firm-wide export's approver is in a real firm.
    for site in sites:
        await seed.member(site, margaret, "engagement_partner")
    engagements = tuple(s.engagement_id for s in sites)
    # DEC-640 packages only an engagement with an asked PBC binder: each site's request list (a
    # PBC binder on the engagement's assurance work item) is published, as the client was asked.
    await seed.run(
        "UPDATE request_lists SET status = 'published', published_at = clock_timestamp() "
        "WHERE tenant_id = $1 AND engagement_id = ANY($2::uuid[])",
        tenant,
        list(engagements),
    )
    return Firm(net, tenant, felix, margaret, second, staff, engagements)


@pytest.fixture
async def firm(net: Net) -> Firm:
    return await _firm(net)


async def _call(
    net: Net,
    method: str,
    path: str,
    who: Person,
    *,
    body: Mapping[str, object] | None = None,
    mfa: bool = True,
    key: str | None = None,
) -> httpx.Response:
    headers = net.headers(who, mfa=mfa)
    if key is not None:
        headers["Idempotency-Key"] = key
    return await net.http.request(method, path, json=body, headers=headers)


async def _request(f: Firm, approver: Person | None = None, *, by: Person | None = None) -> Json:
    target = approver if approver is not None else f.margaret
    response = await _call(
        f.net,
        "POST",
        EXPORTS,
        by if by is not None else f.felix,
        body={"approver_user_id": str(target.user_id), "scope": "all"},
        key=uuid.uuid4().hex,
    )
    assert response.status_code == 202, response.text
    return cast(Json, response.json())


async def _listed(f: Firm, export_id: object, who: Person | None = None) -> Json:
    response = await _call(f.net, "GET", EXPORTS, who if who is not None else f.felix)
    assert response.status_code == 200, response.text
    items = cast(list[Json], cast(Json, response.json())["items"])
    found = [i for i in items if i["id"] == export_id]
    assert len(found) == 1, items
    return found[0]


async def _build(client: Client, f: Firm, export_id: object) -> None:
    await client.execute_workflow(
        FirmExportWorkflow.run,
        FirmExportInput(str(f.tenant_id), str(export_id)),
        id=f"firm_export:{f.tenant_id}:{export_id}",
        task_queue=queue_for("batch"),
    )


async def _ready(f: Firm, client: Client) -> Json:
    requested = await _request(f)
    approved = await _call(f.net, "POST", f"{EXPORTS}/{requested['id']}/approve", f.margaret)
    assert approved.status_code == 200, approved.text
    await _build(client, f, requested["id"])
    ready = await _listed(f, requested["id"])
    assert ready["status"] == "ready", ready
    return ready


async def _link(f: Firm, export_id: object, who: Person | None = None) -> httpx.Response:
    return await _call(f.net, "POST", f"{EXPORTS}/{export_id}/link", who or f.felix)


def _at(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


# --- probes --------------------------------------------------------------------------------------


def _entries(manifest: object) -> list[Json] | None:
    if isinstance(manifest, list):
        return cast(list[Json], manifest)
    if isinstance(manifest, dict):
        files = cast(Json, manifest).get("files")
        if isinstance(files, list):
            return cast(list[Json], files)
    return None


def manifest_problems(archive: bytes, manifest_sha256: str) -> list[str]:
    """What the archive's manifest fails to vouch for (AC-40, DEC-508)."""
    found: list[str] = []
    try:
        bundle = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile:
        return ["the archive is not a ZIP"]
    names = set(bundle.namelist())
    if "manifest.json" not in names or "index.json" not in names:
        return [f"index.json or manifest.json missing: {sorted(names)}"]
    manifest_bytes = bundle.read("manifest.json")
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256:
        found.append("manifest_sha256 is not the digest of manifest.json")
    entries = _entries(json.loads(manifest_bytes))
    if entries is None:
        return [*found, "manifest.json lists no files"]
    listed = {str(e.get("path")): e for e in entries}
    if set(listed) != names - {"manifest.json"}:
        found.append(f"manifest lists {sorted(listed)}, archive holds {sorted(names)}")
    for path, entry in listed.items():
        if path not in names:
            continue
        content = bundle.read(path)
        if entry.get("sha256") != hashlib.sha256(content).hexdigest():
            found.append(f"{path}: SHA-256 does not match")
        if entry.get("bytes") != len(content):
            found.append(f"{path}: bytes do not match")
    index = cast(Json, json.loads(bundle.read("index.json")))
    if index.get("format") is None or not isinstance(index.get("packages"), list):
        found.append("index.json has no format or packages")
    return found


def window_problems(
    export: Mapping[str, object], link: Mapping[str, object], now: datetime
) -> list[str]:
    """What a ready export and a fresh link get wrong about the two windows (AC-41)."""
    found: list[str] = []
    decided, until = _at(export["decided_at"]), _at(export["available_until"])
    if until - decided != WINDOW:
        found.append(f"available_until is {until - decided} after the approval, not 7 days")
    expires = _at(link["expires_at"])
    if expires > now + LINK_LIFE or expires < now + LINK_LIFE - timedelta(minutes=1):
        found.append(f"the link lives {expires - now}, not 15 minutes")
    if expires > until:
        found.append("the link outlives the 7-day window")
    if link["manifest_sha256"] != export["manifest_sha256"]:
        found.append("the link's manifest_sha256 is not the export's")
    return found


# --- AC-40: dual approval ------------------------------------------------------------------------


async def test_ac40_the_requester_approving_is_409_approver_must_differ(firm: Firm) -> None:
    requested = await _request(firm)
    assert requested["status"] == "awaiting_approval"
    assert cast(Json, requested["approver"])["user_id"] == str(firm.margaret.user_id)
    assert cast(Json, requested["requested_by"])["user_id"] == str(firm.felix.user_id)
    response = await _call(firm.net, "POST", f"{EXPORTS}/{requested['id']}/approve", firm.felix)
    assert response.status_code == 409, response.text
    assert cast(Json, response.json())["detail"] == "approver_must_differ"
    assert (await _listed(firm, requested["id"]))["status"] == "awaiting_approval"


async def test_ac40_naming_oneself_or_a_non_partner_as_approver_is_422(firm: Firm) -> None:
    for approver in (firm.felix, firm.staff):
        response = await _call(
            firm.net,
            "POST",
            EXPORTS,
            firm.felix,
            body={"approver_user_id": str(approver.user_id), "scope": "all"},
            key=uuid.uuid4().hex,
        )
        assert response.status_code == 422, response.text
        assert cast(Json, response.json())["detail"] == "approver_invalid"


async def test_ac40_only_a_security_admin_requests(firm: Firm) -> None:
    for who in (firm.margaret, firm.staff):
        response = await _call(
            firm.net,
            "POST",
            EXPORTS,
            who,
            body={"approver_user_id": str(firm.second_admin.user_id), "scope": "all"},
            key=uuid.uuid4().hex,
        )
        assert response.status_code == 403, response.text


async def test_ac40_only_the_named_approver_decides(firm: Firm) -> None:
    requested = await _request(firm)
    for who in (firm.second_admin, firm.staff):
        response = await _call(firm.net, "POST", f"{EXPORTS}/{requested['id']}/approve", who)
        assert response.status_code == 403, (who, response.text)
    assert (await _listed(firm, requested["id"]))["status"] == "awaiting_approval"


async def test_ac40_a_stale_second_factor_cannot_request_or_approve(firm: Firm) -> None:
    stale = await _call(
        firm.net,
        "POST",
        EXPORTS,
        firm.felix,
        body={"approver_user_id": str(firm.margaret.user_id), "scope": "all"},
        mfa=False,
        key=uuid.uuid4().hex,
    )
    assert stale.status_code == 403, stale.text
    assert cast(Json, cast(Json, stale.json()).get("facts") or {}).get("reason") == "mfa_required"
    requested = await _request(firm)
    response = await _call(
        firm.net, "POST", f"{EXPORTS}/{requested['id']}/approve", firm.margaret, mfa=False
    )
    assert response.status_code == 403, response.text
    facts = cast(Json, cast(Json, response.json()).get("facts") or {})
    assert facts.get("reason") == "mfa_required"
    assert (await _listed(firm, requested["id"]))["status"] == "awaiting_approval"


async def test_ac40_the_named_approver_starts_a_sealed_build_with_a_manifest(
    firm: Firm, temporal: Client, raw: S3Client
) -> None:
    requested = await _request(firm)
    approved = await _call(firm.net, "POST", f"{EXPORTS}/{requested['id']}/approve", firm.margaret)
    assert approved.status_code == 200, approved.text
    assert cast(Json, approved.json())["status"] == "building"
    await _build(temporal, firm, requested["id"])
    ready = await _listed(firm, requested["id"])
    assert ready["status"] == "ready"
    digest = str(ready["manifest_sha256"])
    assert len(digest) == 64 and int(digest, 16) >= 0
    # Sealed under the tenant's key: no stored segment is a readable ZIP.
    listing = raw.list_objects_v2(Bucket=ARCHIVES, Prefix=f"exports/{firm.tenant_id}/")
    keys = [o.get("Key", "") for o in listing.get("Contents", [])]
    assert keys, "the archive was not stored"
    for key in keys:
        head = raw.get_object(Bucket=ARCHIVES, Key=key)["Body"].read(4)
        assert head != ZIP_MAGIC, key
    rows = await firm.net.seed.rows(
        "SELECT action, actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action LIKE 'firm_export.%' ORDER BY seq",
        firm.tenant_id,
    )
    seen = {(r["action"], r["actor_kind"]) for r in rows}
    assert ("firm_export.requested", "human") in seen
    assert ("firm_export.approved", "human") in seen
    assert ("firm_export.ready", "system") in seen
    approvers = {r["actor_id"] for r in rows if r["action"] == "firm_export.approved"}
    assert approvers == {str(firm.margaret.user_id)}


async def test_ac40_another_firm_and_flag_off_answer_404(firm: Firm) -> None:
    requested = await _request(firm)
    other = await _firm(firm.net)
    response = await _call(
        firm.net, "POST", f"{EXPORTS}/{requested['id']}/approve", other.margaret
    )
    assert response.status_code == 404, response.text
    off = await _firm(firm.net, flag=False)
    for method, path in (("GET", EXPORTS), ("POST", f"{EXPORTS}/{requested['id']}/link")):
        response = await _call(firm.net, method, path, off.felix)
        assert response.status_code == 404, (path, response.text)


# --- AC-41: links, windows and the manifest ------------------------------------------------------


async def test_ac41_the_archive_verifies_against_its_manifest(
    firm: Firm, temporal: Client
) -> None:
    ready = await _ready(firm, temporal)
    link = await _link(firm, ready["id"])
    assert link.status_code == 200, link.text
    body = cast(Json, link.json())
    assert window_problems(ready, body, datetime.now(UTC)) == []
    archive = await _call(firm.net, "GET", str(body["url"]), firm.felix)
    assert archive.status_code in (200, 206), archive.text
    assert manifest_problems(archive.content, str(ready["manifest_sha256"])) == []


async def test_ac41_a_link_answers_410_after_its_15_minutes(firm: Firm, temporal: Client) -> None:
    ready = await _ready(firm, temporal)
    body = cast(Json, (await _link(firm, ready["id"])).json())
    assert window_problems(ready, body, datetime.now(UTC)) == []  # it lives 15 minutes
    # The link's 15 minutes are a security window on real time (`kernel.clock.system_now`: a
    # demo or frozen business clock never moves one), so the row is aged instead of the clock.
    link_id = uuid.UUID(str(body["url"]).rstrip("/").rsplit("/", 1)[1])
    await firm.net.seed.run_untriggered(
        "UPDATE firm_export_links SET issued_at = issued_at - interval '16 minutes', "
        "expires_at = expires_at - interval '16 minutes' WHERE id = $1",
        link_id,
    )
    response = await _call(firm.net, "GET", str(body["url"]), firm.felix)
    assert response.status_code == 410, response.text
    assert cast(Json, response.json())["detail"] == "link_expired"


async def test_ac41_after_7_days_no_link_is_minted_and_none_opens(
    firm: Firm, temporal: Client
) -> None:
    ready = await _ready(firm, temporal)
    body = cast(Json, (await _link(firm, ready["id"])).json())
    with clock.frozen(_at(ready["available_until"]) + timedelta(seconds=1)):
        minted = await _link(firm, ready["id"])
        opened = await _call(firm.net, "GET", str(body["url"]), firm.felix)
    assert minted.status_code == 410, minted.text
    assert cast(Json, minted.json())["detail"] == "export_expired"
    assert opened.status_code == 410, opened.text
    assert cast(Json, opened.json())["detail"] in ("export_expired", "link_expired")


async def test_ac41_links_are_the_requesters_and_the_approvers_only(
    firm: Firm, temporal: Client
) -> None:
    ready = await _ready(firm, temporal)
    for outsider in (firm.second_admin, firm.staff):
        response = await _link(firm, ready["id"], outsider)
        assert response.status_code == 403, response.text
    approvers = await _link(firm, ready["id"], firm.margaret)
    assert approvers.status_code == 200, approvers.text
    felix_link = cast(Json, (await _link(firm, ready["id"])).json())
    # A link opens only for the signed-in person it was issued to (DEC-509).
    response = await _call(firm.net, "GET", str(felix_link["url"]), firm.margaret)
    assert response.status_code == 404, response.text


async def test_ac41_each_download_needs_a_fresh_second_factor(
    firm: Firm, temporal: Client
) -> None:
    ready = await _ready(firm, temporal)
    stale_link = await _call(
        firm.net, "POST", f"{EXPORTS}/{ready['id']}/link", firm.felix, mfa=False
    )
    assert stale_link.status_code == 403, stale_link.text
    body = cast(Json, (await _link(firm, ready["id"])).json())
    stale = await _call(firm.net, "GET", str(body["url"]), firm.felix, mfa=False)
    assert stale.status_code == 403, stale.text
    downloads = await firm.net.seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'firm_export.downloaded'",
        firm.tenant_id,
    )
    assert len(downloads) == 1  # only the fresh link was issued


async def test_ac41_each_download_leaves_an_access_event(firm: Firm, temporal: Client) -> None:
    ready = await _ready(firm, temporal)
    before = await firm.net.seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id
    )
    body = cast(Json, (await _link(firm, ready["id"])).json())
    archive = await _call(firm.net, "GET", str(body["url"]), firm.felix)
    assert archive.status_code in (200, 206), archive.text
    after = await firm.net.seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id
    )
    assert cast(int, after) > cast(int, before)


# --- Q-02-T47: one verified package per engagement (written before T47; T47 landed in #501) ---


async def test_ac40_t47_the_archive_holds_one_verified_package_per_engagement(
    firm: Firm, temporal: Client
) -> None:
    ready = await _ready(firm, temporal)
    body = cast(Json, (await _link(firm, ready["id"])).json())
    archive = await _call(firm.net, "GET", str(body["url"]), firm.felix)
    assert archive.status_code in (200, 206), archive.text
    assert manifest_problems(archive.content, str(ready["manifest_sha256"])) == []
    bundle = zipfile.ZipFile(io.BytesIO(archive.content))
    index = cast(Json, json.loads(bundle.read("index.json")))
    packages = cast(list[object], index["packages"])
    assert len(packages) == len(firm.engagements)
    for engagement in firm.engagements:
        naming = [p for p in packages if str(engagement) in json.dumps(p)]
        assert len(naming) == 1, engagement
    # Every package file is in the archive and vouched for by the manifest (checked above), so
    # the archive holds more than the index and the manifest.
    assert len(bundle.namelist()) > 2


# --- the probes and the database catch planted violations ----------------------------------------


def _rezip(archive: bytes, change: Callable[[str, bytes], bytes]) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(archive))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as target:
        for name in source.namelist():
            target.writestr(name, change(name, source.read(name)))
    return out.getvalue()


async def test_seeded_manifest_violations_are_caught(firm: Firm, temporal: Client) -> None:
    ready = await _ready(firm, temporal)
    body = cast(Json, (await _link(firm, ready["id"])).json())
    archive = (await _call(firm.net, "GET", str(body["url"]), firm.felix)).content
    digest = str(ready["manifest_sha256"])
    assert manifest_problems(archive, digest) == []
    tampered_index = _rezip(archive, lambda n, b: b + b" " if n == "index.json" else b)
    assert manifest_problems(tampered_index, digest)
    tampered_manifest = _rezip(archive, lambda n, b: b + b" " if n == "manifest.json" else b)
    assert manifest_problems(tampered_manifest, digest)
    assert manifest_problems(archive, "0" * 64)
    extra = io.BytesIO(archive)
    with zipfile.ZipFile(extra, "a") as bundle:
        bundle.writestr("unlisted.json", b"{}")
    assert manifest_problems(extra.getvalue(), digest)


async def test_seeded_window_violations_are_caught(firm: Firm, temporal: Client) -> None:
    ready = await _ready(firm, temporal)
    link = cast(Json, (await _link(firm, ready["id"])).json())
    now = datetime.now(UTC)  # after the link is minted, so its 15 minutes run from before now
    assert window_problems(ready, link, now) == []
    decided = _at(ready["decided_at"])
    planted: list[tuple[Json, Json]] = [
        ({**ready, "available_until": (decided + WINDOW * 2).isoformat()}, link),
        (ready, {**link, "expires_at": (now + timedelta(hours=1)).isoformat()}),
        (ready, {**link, "manifest_sha256": "0" * 64}),
    ]
    for export, minted in planted:
        assert window_problems(export, minted, now), (export, minted)


async def test_seeded_one_person_as_both_halves_is_refused_by_the_database(firm: Firm) -> None:
    requested = await _request(firm)
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.net.seed.run_untriggered(
            "UPDATE firm_exports SET approver_id = requested_by WHERE id = $1",
            uuid.UUID(str(requested["id"])),
        )
