"""P-03-T16 against Postgres and the S3 gateway (SPEC-322 AC-26 to AC-29; C4 §3.5; DEC-60,
DEC-370): "An onshore engagement member gets the value with expires_in 30 and an audit row naming
them, while an offshore member, an agent or a client principal is refused and nothing is
revealed."

Through the service inside a recorded request (`recording_checks`, as a route serves it): the
value comes back formatted, with one `pii_reveals` row, one `pii.revealed` audit event naming the
person and one access event, none holding the value. Every refusal leaves no reveal row, no
audit event and no access event. MFA outside the window is 403 `mfa_required`; the 21st reveal in
an hour is 429.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from structlog.testing import capture_logs

from abacus.kernel.errors import NotFound
from abacus.modules.evidence import reveals
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.masked_previews import masked_preview_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.reveals import (
    REVEAL_LIMIT,
    RevealNeedsMfa,
    RevealRateLimited,
    reveal_pii,
)
from abacus.modules.evidence.viewer import viewer_manifest
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import AuthContext, Forbidden, agent_context_for_run
from abacus.modules.identity.authz import recording_checks
from abacus_tools.synthetic.documents import w2_pdf

from .support import Firm, Seeder, as_version, make_firm

VALUE = "000-00-6081"
DUMPS = (
    "SELECT coalesce(string_agg(t::text, ''), '') FROM pii_reveals t WHERE tenant_id = $1",
    "SELECT coalesce(string_agg(t::text, ''), '') FROM audit_events t WHERE tenant_id = $1",
    "SELECT coalesce(string_agg(t::text, ''), '') FROM access_events t WHERE tenant_id = $1",
    "SELECT coalesce(string_agg(t::text, ''), '') FROM outbox t WHERE tenant_id = $1",
)


async def _w2(firm: Firm) -> tuple[uuid.UUID, uuid.UUID]:
    """The W-2 through the v7 pipeline, the reveal flag on; its SSN region's id."""
    await firm.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'evidence.pii_reveal', 'true', 'test-seed', 'P-03-T16') "
        "ON CONFLICT DO NOTHING",
        firm.tenant_id,
    )
    version = await firm.version(w2_pdf())
    given = as_version(firm, version)
    await extract_upload(given)
    await words_upload(given)
    await pii_scan_upload(given)
    await masked_preview_upload(given)
    region = await firm.seed.id(
        "SELECT id FROM pii_regions WHERE evidence_version_id = $1 AND kind = 'ssn'", version
    )
    return version, region


async def _reveal(ctx: object, version: uuid.UUID, region: uuid.UUID) -> reveals.RevealedPii:
    with recording_checks():
        return await reveal_pii(ctx, version, region, None)  # type: ignore[arg-type]  # a refused principal on purpose


async def _traces(seed: Seeder, firm: Firm) -> tuple[int, int, int]:
    reveals_n = await seed.value(
        "SELECT count(*) FROM pii_reveals WHERE tenant_id = $1", firm.tenant_id
    )
    audits = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'pii.revealed'",
        firm.tenant_id,
    )
    access = await seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND kind = 'pii.revealed'",
        firm.tenant_id,
    )
    return int(str(reveals_n)), int(str(audits)), int(str(access))


async def test_ac26_an_onshore_member_gets_the_value_and_a_logged_record(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version, region = await _w2(firm)
    manifest = await viewer_manifest(firm.person(), version)
    assert manifest.allowed_actions == ["pii.reveal"]
    with capture_logs() as logs:
        revealed = await _reveal(firm.person(), version, region)
    assert (revealed.value, revealed.kind, revealed.expires_in) == (VALUE, "ssn", 30)
    assert revealed.mask_id == region and revealed.revealed_by == "Test person"
    [row] = await seed.rows(
        "SELECT user_id, region_id, reason_code, mfa_at, actor_kind, "
        "expires_at - revealed_at AS lasts FROM pii_reveals WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert (row["user_id"], row["region_id"], row["reason_code"], row["actor_kind"]) == (
        firm.user_id,
        region,
        "source_review",
        "human",
    )
    assert row["mfa_at"] is not None and row["lasts"] == timedelta(seconds=30)
    [audit] = await seed.rows(
        "SELECT actor_id, target_type, target_id, after_ref::text AS after FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'pii.revealed'",
        firm.tenant_id,
    )
    assert (audit["actor_id"], audit["target_type"], audit["target_id"]) == (
        str(firm.user_id),
        "evidence_version",
        str(version),
    )
    assert str(region) in audit["after"]
    [access] = await seed.rows(
        "SELECT kind, subject_type, subject_id, flags FROM access_events WHERE tenant_id = $1 "
        "AND kind = 'pii.revealed'",
        firm.tenant_id,
    )
    assert (access["subject_type"], access["subject_id"]) == ("pii_region", region)
    assert "pii_tin" in access["flags"]
    # The value is in no table but its sealed envelope, and in no log line.
    for query in DUMPS:
        dumped = await seed.value(query, firm.tenant_id)
        assert "6081" not in str(dumped).replace(str(region), ""), query
    assert all("6081" not in str(entry) for entry in logs)


async def test_ac28_offshore_agent_client_and_support_are_refused_and_nothing_is_revealed(
    seed: Seeder,
) -> None:
    firm = await make_firm(seed)
    version, region = await _w2(firm)
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.upload_reviewer",
        engagement_id=firm.engagement_id,
        task_scope=frozenset({"evidence.read", "pii.reveal"}),
        initiator_user_id=firm.user_id,
    )
    client = dataclasses.replace(firm.person(), client=True)
    support = dataclasses.replace(
        firm.person(),
        tenant=dataclasses.replace(firm.person().tenant, actor_kind="support"),
    )
    for refused in (agent, client, support):
        with pytest.raises(Forbidden):
            await _reveal(refused, version, region)
    # Outside a request being served (a worker, a script): refused even for the person.
    with pytest.raises(Forbidden):
        await reveal_pii(firm.person(), version, region, None)
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.user_id,
    )
    with pytest.raises(Forbidden) as offshore:
        await _reveal(firm.person(), version, region)
    assert offshore.value.layer == "condition"
    assert (await viewer_manifest(firm.person(), version)).allowed_actions == []  # no chip
    assert await _traces(seed, firm) == (0, 0, 0)


async def test_ac27_mfa_outside_the_window_answers_mfa_required(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version, region = await _w2(firm)
    for mfa_at in (None, datetime.now(UTC) - timedelta(minutes=20)):
        stale = dataclasses.replace(firm.person(), mfa_at=mfa_at)
        with pytest.raises(RevealNeedsMfa) as refused:
            await _reveal(stale, version, region)
        assert refused.value.facts == {"reason": "mfa_required"}
    assert await _traces(seed, firm) == (0, 0, 0)


async def test_a_region_of_another_version_or_firm_is_not_found(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version, _region = await _w2(firm)
    other, other_region = await _w2(firm)
    with pytest.raises(NotFound):
        await _reveal(firm.person(), version, other_region)  # not on this version
    elsewhere = await make_firm(seed)
    with pytest.raises(NotFound):
        await _reveal(elsewhere.person(), other, other_region)  # another firm's version
    outsider: AuthContext = firm.person(await firm.outsider())
    with pytest.raises((NotFound, Forbidden)):
        await _reveal(outsider, other, other_region)  # not on the engagement
    assert await _traces(seed, firm) == (0, 0, 0)


async def test_ac29_the_twenty_first_reveal_in_an_hour_is_refused(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    firm = await make_firm(seed)
    version, region = await _w2(firm)
    for _ in range(REVEAL_LIMIT):
        await _reveal(firm.person(), version, region)
    with pytest.raises(RevealRateLimited) as limited:
        await _reveal(firm.person(), version, region)
    assert limited.value.facts["limit"] == REVEAL_LIMIT
    assert 0 < int(limited.value.facts["retry_after"]) <= 3600
    assert await _traces(seed, firm) == (REVEAL_LIMIT, REVEAL_LIMIT, REVEAL_LIMIT)
    throttled = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'pii.reveal_throttled'",
        firm.tenant_id,
    )
    assert throttled == 1
