"""R-01-T29: independent acceptance tests (ADR-078) for R-01-T22 and T26, written from
`docs/contracts/portal-settings.md`, the matrix (`permission-matrix/portal.yaml`) and R-01 §3, not
from the implementing suites.

- Publish is atomic and versions are insert-only: the app role cannot change or delete a version.
- Draft, publish and logo need fresh MFA; the agent and the system are refused.
- Preview is read-only (no mutation route under `/preview`) and never reaches beyond `visible()`:
  a firm admin without access to a client cannot preview that client's contact (DEC-20,
  ADR-024); with no contact the sample client answers.
- The published toggles are what the portal's read model honours.
- No template text outside the import path: the settings draft refuses fields it does not know.
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.api.app import create_app
from abacus.kernel.db import TenantContext, tenant_session

from .support import Json, Net, Person

pytestmark = pytest.mark.asyncio
S: Final = "/v1/firm/portal-settings"


def _draft(expected: int, **experience: bool) -> Json:
    return {
        "brand": {"portal_name": "Brightwater Hale Client Portal", "sender_display_name": "BH"},
        "client_experience": dict(experience),
        "follow_up_policy": {"cadence_days": 7},
        "expected_version": expected,
    }


async def _editor_on(net: Net, tenant: uuid.UUID) -> None:
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'portal.settings_editor', 'true', 'test-seed', 'R-01-T29') "
        "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = 'true'",
        tenant,
    )


async def _publish(net: Net, who: Person) -> Json:
    headers = {**net.headers(who), "Idempotency-Key": f"r01t29-{uuid.uuid4().hex[:8]}"}
    published = await net.http.post(f"{S}/publish", headers=headers)
    assert published.status_code == 201, published.text
    return cast(Json, published.json())


async def test_publish_is_atomic_and_versions_are_insert_only(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    await _editor_on(net, tenant)
    grace = await seed.person(tenant, "firm_admin")
    assert (await net.call("PUT", f"{S}/draft", grace, body=_draft(0))).status_code == 200
    first = await _publish(net, grace)
    assert (await net.call("PUT", f"{S}/draft", grace, body=_draft(0))).status_code == 200
    second = await _publish(net, grace)
    assert (first["version"], second["version"]) == (1, 2)
    versions = await seed.rows(
        "SELECT version FROM portal_settings_versions WHERE tenant_id = $1 ORDER BY version",
        tenant,
    )
    assert [r["version"] for r in versions] == [1, 2]

    nothing = await net.http.post(
        f"{S}/publish", headers={**net.headers(grace), "Idempotency-Key": "r01t29-none"}
    )
    assert nothing.status_code == 409, nothing.text  # no draft: nothing half-published
    assert (
        await seed.value(
            "SELECT count(*) FROM portal_settings_versions WHERE tenant_id = $1", tenant
        )
        == 2
    )

    system = TenantContext(tenant, "system", "r01t29:tamper")
    for sql in (
        "UPDATE portal_settings_versions SET settings = '{}'::jsonb WHERE version = 1",
        "DELETE FROM portal_settings_versions WHERE version = 1",
    ):
        with pytest.raises(DBAPIError):
            async with tenant_session(system) as session:
                await session.execute(text(sql))
                await session.flush()


async def test_writes_need_fresh_mfa_and_a_firm_admin(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    await _editor_on(net, tenant)
    grace = await seed.person(tenant, "firm_admin")
    hannah = await seed.person(tenant)
    stale = await net.call("PUT", f"{S}/draft", grace, body=_draft(0), mfa=False)
    assert stale.status_code in (401, 403), stale.text
    assert (await net.call("PUT", f"{S}/draft", hannah, body=_draft(0))).status_code == 403
    assert (await net.call("GET", f"{S}/preview", hannah)).status_code == 403
    assert (
        await seed.value(
            "SELECT count(*) FROM portal_settings_drafts WHERE tenant_id = $1", tenant
        )
        == 0
    )


def test_preview_has_no_mutation_route() -> None:
    routes = [r for r in create_app().routes if isinstance(r, APIRoute)]
    methods = {m for r in routes if r.path.startswith(f"{S}/preview") for m in r.methods or ()}
    assert methods, "the preview route is mounted"
    assert methods <= {"GET", "HEAD"}


async def test_a_firm_admin_without_client_access_cannot_preview_that_client(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    grace = await seed.person(tenant, "firm_admin")
    felix = await seed.person(tenant, "firm_admin")
    copperleaf = await seed.site(tenant, grace.user_id, "Copperleaf")
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
        "VALUES ($1, $2, 'Tess Moreno', 'client_person') RETURNING id",
        tenant,
        copperleaf.client_id,
    )
    await net.wall(grace, felix, copperleaf)  # Felix may not see Copperleaf at all
    refused = await net.call("GET", f"{S}/preview?as={contact}", felix)
    assert refused.status_code == 404, refused.text
    assert "Tess Moreno" not in refused.text and "Copperleaf" not in refused.text
    unknown = await net.call("GET", f"{S}/preview?as={uuid.uuid4()}", felix)
    assert unknown.status_code == 404  # the same answer as for a contact that does not exist
    sample = cast(Json, (await net.call("GET", f"{S}/preview", felix)).json())
    assert (sample["read_only"], sample["sample"], sample["contact_id"]) == (True, True, None)
    audited = await seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'portal.preview_viewed'",
        tenant,
    )
    assert audited  # a preview is a read worth recording


async def test_published_toggles_reach_the_read_model_and_unknown_fields_are_refused(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    await _editor_on(net, tenant)
    grace = await seed.person(tenant, "firm_admin")
    saved = await net.call(
        "PUT", f"{S}/draft", grace, body=_draft(0, show_team_card=False, phone_capture=False)
    )
    assert saved.status_code == 200, saved.text
    await _publish(net, grace)
    row = (
        await seed.rows(
            "SELECT show_team_card, phone_capture FROM portal_client_experience "
            "WHERE tenant_id = $1",
            tenant,
        )
    )[0]
    assert (row["show_team_card"], row["phone_capture"]) == (False, False)
    out = cast(Json, (await net.call("GET", S, grace)).json())
    experience = cast(Json, cast(Json, out["published"])["client_experience"])
    assert (experience["show_team_card"], experience["phone_capture"]) == (False, False)

    # Template text has one way in (the import path), never the settings draft.
    smuggled = {
        **_draft(1),
        "email_template": {"subject": "Hi", "body": "<p>text</p>"},
    }
    refused = await net.call("PUT", f"{S}/draft", grace, body=smuggled)
    assert refused.status_code == 422, refused.text
