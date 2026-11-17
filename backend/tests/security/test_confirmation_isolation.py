# ac-test-author: ayushkbhatia
"""A-08-T34 (TASK-8405; ADR-078 independent AC tests for A-08-T15 and A-08-T19; ADR-146 P-09 and
the ADR-152 amendment; SPEC-657 F7; I-CONFIRMATION-ISOLATION).

Written from SPEC-657 AC-7.1 to AC-7.6, `docs/contracts/confirmations.md` (the public family)
and A-08 §3 F7, not from the implementation, against the HTTP surface and the link principal:

- **no enumeration**: unknown, expired, revoked and locked tokens answer one body, one status
  and the padded floor (`_indistinguishable` is the judgement);
- **OTP lockout**: five wrong codes lock the link; the right code then fails too;
- **single answer**: a second submission is 409 `already_answered` and writes nothing;
- **expiry**: an expired link resolves to nothing and verifies nothing;
- **other confirmations unreachable**: a verified link answers only for its own confirmation,
  and cannot cite another link's upload;
- **client token 404**: a client principal never reaches the firm's confirmation routes;
- **hostile attachments**: an infected file is refused and nothing is stored;
- **kill switch**: `confirmation_links` on turns every link into the uniform view.

`test_the_judgement_catches_*` proves the judgement fails on a planted difference, so a build
that leaks any of these fails the suite.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import httpx
import pytest
import yaml
from testcontainers.core.container import DockerContainer
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import uow
from abacus.modules.assurance import confirmations_respondent as respondent
from abacus.modules.assurance import confirmations_service as cs
from abacus.modules.assurance.confirmations_contract import CONFIRM_PAD_SECONDS, LINK_PURPOSE
from abacus.modules.assurance.confirmations_contract_models import (
    ConfirmationCreateIn,
    ConfirmationLineIn,
)
from abacus.modules.evidence import storage
from abacus.modules.identity import link_principals as lp
from abacus.modules.identity.api import AuthContext

from .support import Seeder

pytestmark = pytest.mark.asyncio
EMAIL = "ap@customer.example"
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def _indistinguishable(answers: Sequence[tuple[int, bytes, float]]) -> bool:
    """The judgement: one status, one body, and every answer at or past the padded floor."""
    statuses = {a[0] for a in answers}
    bodies = {a[1] for a in answers}
    floor = all(a[2] >= CONFIRM_PAD_SECONDS * 0.95 for a in answers)
    return len(statuses) == 1 and len(bodies) == 1 and floor


def test_the_judgement_catches_a_planted_body_difference() -> None:
    assert not _indistinguishable([(200, b'{"state":"expired"}', 1.0), (200, b"{}", 1.0)])


def test_the_judgement_catches_a_planted_timing_oracle() -> None:
    assert not _indistinguishable([(200, b"x", CONFIRM_PAD_SECONDS), (200, b"x", 0.0)])


async def _firm(seed: Seeder) -> tuple[AuthContext, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant, "firm_admin")
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Granite Peak') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Granite "
        "Peak') RETURNING id",
        tenant,
        client,
    )
    engagement = await seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by, status) VALUES ($1, $2, $3, "
        "'FY2026 Audit', '2026-01-01', '2026-12-31', $4, 'active') RETURNING id",
        tenant,
        client,
        entity,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) VALUES ($1, "
        "$2, $3, 'engagement_partner')",
        tenant,
        engagement,
        person.user_id,
    )
    work_item = uuid.UUID(
        str(
            await seed.value(
                "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
                engagement,
            )
        )
    )
    ctx = AuthContext(
        TenantContext(tenant, "human", str(person.user_id)),
        person.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )
    return ctx, work_item


async def _sent(
    ctx: AuthContext, work_item: uuid.UUID, seed: Seeder, n: int
) -> tuple[uuid.UUID, str]:
    row = await cs.create(
        ctx,
        work_item,
        ConfirmationCreateIn(
            type="accounts_receivable",
            respondent_name=f"Respondent {n}",
            respondent_org=f"Customer {n}",
            channel="accrued_link",
            address_value=EMAIL,
            lines=[ConfirmationLineIn(description="Balance", book_amount=Decimal("1000.00"))],
        ),
    )
    await seed.run("UPDATE confirmations SET status = 'sent' WHERE id = $1", row.id)
    async with uow(ctx.tenant) as tx:
        token = await lp.mint_link(
            tx,
            tenant_id=ctx.tenant_id,
            purpose=LINK_PURPOSE,
            subject_id=row.id,
            email=EMAIL,
            created_by=ctx.user_id,
            valid_for=timedelta(days=30),
        )
    return row.id, token


async def _code(seed: Seeder, token: str) -> str:
    await lp.request_code(token, EMAIL)
    challenge = uuid.UUID(
        str(
            await seed.value(
                "SELECT c.id FROM link_principal_challenges c JOIN link_principals p ON "
                "p.id = c.principal_id WHERE p.token_sha256 = $1 ORDER BY c.created_at DESC "
                "LIMIT 1",
                lp.sha256(token),
            )
        )
    )
    issued = await lp.issue_link_code(challenge)
    assert issued is not None
    return issued.code


async def _view(http: httpx.AsyncClient, token: str) -> tuple[int, bytes, float]:
    started = time.monotonic()
    answer = await http.get(f"/v1/confirm/{token}")
    return answer.status_code, answer.content, time.monotonic() - started


async def test_no_enumeration_unknown_expired_revoked_locked(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    ctx, work_item = await _firm(seed)
    _, expired = await _sent(ctx, work_item, seed, 1)
    _, revoked = await _sent(ctx, work_item, seed, 2)
    _, locked = await _sent(ctx, work_item, seed, 3)
    await seed.run(
        "UPDATE link_principals SET created_at = created_at - interval '40 days', expires_at = "
        "created_at - interval '10 days' WHERE token_sha256 = $1",
        lp.sha256(expired),
    )
    await seed.run(
        "UPDATE link_principals SET revoked_at = now() WHERE token_sha256 = $1", lp.sha256(revoked)
    )
    await lp.request_code(locked, EMAIL)
    for _ in range(lp.MAX_TRIES):
        await lp.verify_code(locked, "000000")
    answers = [await _view(http, t) for t in ("u" * 43, expired, revoked, locked)]
    assert _indistinguishable(answers)


async def test_otp_lockout_after_five_wrong_codes(seed: Seeder) -> None:
    ctx, work_item = await _firm(seed)
    _, token = await _sent(ctx, work_item, seed, 1)
    code = await _code(seed, token)
    wrong = "111111" if code != "111111" else "222222"
    for _ in range(lp.MAX_TRIES):
        assert await lp.verify_code(token, wrong) is None
    assert await lp.verify_code(token, code) is None  # locked: the right code fails too
    assert await lp.resolve_link(token) is None


async def test_single_answer(seed: Seeder) -> None:
    ctx, work_item = await _firm(seed)
    confirmation, token = await _sent(ctx, work_item, seed, 1)
    code = await _code(seed, token)
    verified = await lp.verify_code(token, code)
    assert verified is not None
    principal = await lp.credential_principal(verified.credential, verified.csrf)
    assert principal is not None and principal.subject_id == confirmation
    await respondent.submit(
        principal, agrees=True, balance=None, respondent_name="A. Payable", explanation=None,
        attachment_ids=[],
    )  # fmt: skip
    responses = await seed.value(
        "SELECT count(*) FROM confirmation_responses WHERE confirmation_id = $1", confirmation
    )
    with pytest.raises(respondent.AlreadyAnswered):
        await respondent.submit(
            principal, agrees=False, balance=Decimal("1.00"), respondent_name="B", explanation="x",
            attachment_ids=[],
        )  # fmt: skip
    assert (
        await seed.value(
            "SELECT count(*) FROM confirmation_responses WHERE confirmation_id = $1", confirmation
        )
        == responses
    )


async def test_expiry_resolves_and_verifies_nothing(seed: Seeder) -> None:
    ctx, work_item = await _firm(seed)
    _, token = await _sent(ctx, work_item, seed, 1)
    code = await _code(seed, token)
    await seed.run(
        "UPDATE link_principals SET created_at = created_at - interval '40 days', expires_at = "
        "created_at - interval '10 days' WHERE token_sha256 = $1",
        lp.sha256(token),
    )
    assert await lp.resolve_link(token) is None
    assert await lp.verify_code(token, code) is None


# --- object storage, as tests/security/test_upload_hostile_files.py runs it (ADR-077) -----------
# A second confirmation's letter reaches evidence storage; without this the settings name the dev
# gateway on 7070, present on a laptop running `make dev` and absent on CI.
_REPO: Final = Path(__file__).resolve().parents[3]
_BUCKET: Final = "abacus-confirmation-isolation"
_MASTER: Final = b"confirmation-isolation-master-key-01234567"
_S3_ACCESS: Final = "abacus"  # the compose S3 image's fixed local credentials
_S3_ROOT_KEY: Final = "abacuslocal"


def _image(service: str) -> str:
    loaded = cast(dict[str, object], yaml.safe_load((_REPO / "docker-compose.yml").read_text()))
    return str(cast(dict[str, dict[str, object]], loaded["services"])[service]["image"])


@pytest.fixture(scope="module")
def _bucket() -> Iterator[S3Client]:
    container = (
        DockerContainer(_image("s3"))
        .with_env("ROOT_ACCESS_KEY", _S3_ACCESS)
        .with_env("ROOT_SECRET_KEY", _S3_ROOT_KEY)
        .with_command("--health /health posix --versioning-dir /versions /data")
        .with_tmpfs_mount("/data")
        .with_tmpfs_mount("/versions")
        .with_exposed_ports(7070)
    )
    with container:
        endpoint = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(7070)}"
        deadline = time.monotonic() + 60
        while True:
            try:
                if httpx.get(f"{endpoint}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                if time.monotonic() > deadline:
                    raise
            time.sleep(0.5)
        client = s3_client(
            endpoint_url=endpoint,
            access_key=_S3_ACCESS,
            secret_key=_S3_ROOT_KEY,
            region="us-east-1",
        )
        client.create_bucket(Bucket=_BUCKET, ObjectLockEnabledForBucket=True)
        yield client


@pytest.fixture
def evidence_storage(_bucket: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(_MASTER))
    storage.configure_storage(_bucket, _BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.mark.usefixtures("evidence_storage")
async def test_other_confirmations_are_unreachable(seed: Seeder) -> None:
    ctx, work_item = await _firm(seed)
    first, one = await _sent(ctx, work_item, seed, 1)
    second, two = await _sent(ctx, work_item, seed, 2)
    a = await lp.verify_code(one, await _code(seed, one))
    b = await lp.verify_code(two, await _code(seed, two))
    assert a is not None and b is not None
    pa = await lp.credential_principal(a.credential, a.csrf)
    pb = await lp.credential_principal(b.credential, b.csrf)
    assert pa is not None and pb is not None
    assert pa.subject_id == first and pb.subject_id == second
    # Mixing one link's credential with the other's CSRF value proves nothing.
    assert await lp.credential_principal(a.credential, b.csrf) is None
    # B's upload cannot be cited by A's answer.
    uploaded, _ = await respondent.attach(pb, "statement.pdf", b"%PDF-1.4 statement")
    with pytest.raises(respondent.AttachmentNotYours):
        await respondent.submit(
            pa, agrees=True, balance=None, respondent_name="A", explanation=None,
            attachment_ids=[uploaded],
        )  # fmt: skip


async def test_a_client_principal_gets_404_on_firm_routes(seed: Seeder) -> None:
    ctx, work_item = await _firm(seed)
    await _sent(ctx, work_item, seed, 1)
    client_ctx = AuthContext(
        TenantContext(ctx.tenant_id, "human", str(ctx.user_id)),
        ctx.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
        client=True,
    )
    with pytest.raises(NotFound):
        await cs.confirmation_list(client_ctx, work_item)


async def test_hostile_attachment_is_refused_and_nothing_stored(seed: Seeder) -> None:
    ctx, work_item = await _firm(seed)
    confirmation, token = await _sent(ctx, work_item, seed, 1)
    verified = await lp.verify_code(token, await _code(seed, token))
    assert verified is not None
    principal = await lp.credential_principal(verified.credential, verified.csrf)
    assert principal is not None
    with pytest.raises(Exception) as refused:
        await respondent.attach(principal, "invoice.pdf.exe", EICAR)
    assert getattr(refused.value, "code", "") in {"file_refused", "file_type_refused"}
    assert (
        await seed.value(
            "SELECT count(*) FROM confirmation_attachments WHERE confirmation_id = $1",
            confirmation,
        )
        == 0
    )


async def _real_controls() -> frozenset[tuple[str, str, uuid.UUID | None, str | None]]:
    """The app's own read of `platform_control_state()` (tests/conftest.py stubs it outside
    integration, so a switch test reads the real rows itself)."""
    from sqlalchemy import text

    from abacus.kernel.db import platform_transaction

    async with platform_transaction("platform:controls") as conn:
        rows = (await conn.execute(text("SELECT * FROM platform_control_state()"))).all()
    return frozenset((r.control, r.scope, r.tenant_id, r.route) for r in rows)


async def test_kill_switch_turns_every_link_off(
    seed: Seeder, http: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus.kernel import controls

    monkeypatch.setattr(controls, "_read", _real_controls)
    ctx, work_item = await _firm(seed)
    _, token = await _sent(ctx, work_item, seed, 1)
    assert await lp.resolve_link(token) is not None
    unknown = await _view(http, "k" * 43)
    await seed.run(
        "INSERT INTO platform_controls (control, scope, tenant_id, active, reason, set_by, "
        "version) VALUES ('confirmation_links', 'firm', $1, true, 'drill', 'operator:test', 1)",
        ctx.tenant_id,
    )
    from abacus.kernel.controls import forget_controls

    forget_controls()
    assert await lp.resolve_link(token) is None
    paused = await _view(http, token)
    assert _indistinguishable([unknown, paused])
