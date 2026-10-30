"""K-01-T12 (TASK-2122; K-01 §3.4): KNW-03's reads, the `methodology_step` citable and the export.

Acceptance (K-01.tasks.csv): a `methodology_step` citation to BH-EBP-110 step 4 at v3 verifies,
the same key at v2 resolves to its v2 step, and two exports of v3 are byte-identical. Also: the
programs tree counts, a program's steps in number order with anchors, and an unknown key is 404.
The workbooks are the K-01-T05 suite's synthetic ones (no firm content: rule 16).
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.agents.methodology_citations import verify_methodology_step
from abacus.modules.evidence.api import CitationAnchor, CitationClaim, CitationVerdict
from abacus.modules.identity.api import AuthContext

from .support import Net
from .test_k01t05_methodology_programs import (  # the K-01-T05 suite's synthetic workbook
    _flags,  # pyright: ignore[reportPrivateUsage] -- shared fixture builder
    _import,  # pyright: ignore[reportPrivateUsage] -- shared fixture builder
    _workbook,  # pyright: ignore[reportPrivateUsage] -- shared fixture builder
)

pytestmark = pytest.mark.asyncio


async def _two_versions(net: Net) -> tuple[uuid.UUID, dict[str, str], uuid.UUID, uuid.UUID]:
    tenant = await net.seed.firm()
    admin = await net.seed.person(tenant, "firm_admin")
    await _flags(net, tenant, "methodology.programs")
    v2 = await _import(net, admin, "BH Audit Methodology", _workbook())
    v3 = await _import(net, admin, "BH Audit Methodology", _workbook(changed=4))
    return tenant, net.headers(admin), v2, v3


async def test_ac_the_same_key_resolves_to_its_step_at_each_version(net: Net) -> None:
    _tenant, headers, v2, v3 = await _two_versions(net)
    for version in (v2, v3):
        response = await net.http.get(
            "/v1/methodology/steps/resolve",
            params={"key": "bh-ebp-110-4", "version": str(version)},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = cast(dict[str, object], response.json())
        assert body["program_code"] == "BH-EBP-110" and body["number"] == 4
        assert cast(str, body["anchor"]).startswith("bh-ebp-110-4@v")
        assert body["version_id"] == str(version)
    missing = await net.http.get(
        "/v1/methodology/steps/resolve",
        params={"key": "bh-ebp-999-1", "version": str(v3)},
        headers=headers,
    )
    assert missing.status_code == 404


async def test_ac_two_exports_of_v3_are_byte_identical(net: Net) -> None:
    _tenant, headers, _v2, v3 = await _two_versions(net)
    first = await net.http.get(f"/v1/methodology/versions/{v3}/export.xlsx", headers=headers)
    second = await net.http.get(f"/v1/methodology/versions/{v3}/export.xlsx", headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert first.content == second.content


async def test_the_programs_tree_and_steps_read_in_order(net: Net) -> None:
    _tenant, headers, _v2, v3 = await _two_versions(net)
    tree = await net.http.get(f"/v1/methodology/versions/{v3}/programs", headers=headers)
    assert tree.status_code == 200, tree.text
    programs = cast(list[dict[str, object]], tree.json())
    assert [p["code"] for p in programs][:2] == ["BH-EBP-110", "BH-EBP-120"]
    assert [p["step_count"] for p in programs] == [16, 8, 6, 8, 10, 7, 12]
    steps = await net.http.get(
        f"/v1/methodology/programs/{programs[0]['id']}/steps", headers=headers
    )
    rows = cast(list[dict[str, object]], steps.json())
    assert [r["number"] for r in rows] == list(range(1, 17))
    assert rows[3]["text"] == "Step 4 of program 1 (revised)"


async def test_ac_a_methodology_step_citation_verifies_at_v3(net: Net) -> None:
    tenant, _headers, _v2, v3 = await _two_versions(net)
    admin = await net.seed.person(tenant, "firm_admin")
    membership = cast(
        uuid.UUID,
        await net.seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            admin.user_id,
        ),
    )
    ctx = AuthContext(
        TenantContext(tenant, "human", str(admin.user_id)),
        admin.user_id,
        membership,
        "firm_admin",
        datetime.now(UTC),
    )
    claim = CitationClaim(
        "methodology_step",
        {"template_version_id": str(v3), "step_key": "bh-ebp-110-4"},
        quote="Step 4 of program 1",
    )
    anchor = CitationAnchor("workpaper", uuid.uuid4())
    verdict = await _verify(ctx, claim, anchor)
    assert verdict.verified, verdict.reason
    assert verdict.match_id is not None and verdict.match_id.startswith("step:bh-ebp-110-4@v")
    wrong = CitationClaim(claim.kind, claim.locator, quote="not in the step")
    refused = await _verify(ctx, wrong, anchor)
    assert refused.reason == "quote_not_found"


class _ReadOnly(Exception):
    """Rolls back a unit of work that only read: the verifier writes nothing to audit."""


async def _verify(
    ctx: AuthContext, claim: CitationClaim, anchor: CitationAnchor
) -> CitationVerdict:
    found: list[CitationVerdict] = []
    with contextlib.suppress(_ReadOnly):
        async with uow(ctx.tenant) as tx:
            found.append(await verify_methodology_step(tx, ctx, claim, anchor))
            raise _ReadOnly
    return found[0]
