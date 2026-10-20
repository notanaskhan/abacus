"""SPEC-002 AC-4, AC-5: a walled person cannot read the client's engagement through any list or
search the app offers, whatever their role.

Each test has its own firm with a walled client A and an unrelated client B, both with an open
engagement, a request item and an evidence version. The person is a member of both engagements
(so every surface would show both) and is walled off from A through the API. For each surface
the control must hold too: B appears for the person, so a surface that is simply empty or
forbidden cannot pass by accident. Expectations come from the spec, not the implementation.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from .support import ROLES, STAFF_ROLES, Env, Seeder

# --- AC-5: lists and searches ---------------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac5_the_engagement_list_shows_nothing_of_the_walled_client(
    env: Env, role: str
) -> None:
    who = await env.walled(role)
    response = await env.get(who, "/v1/engagements")
    assert response.status_code == 200, response.text
    assert env.leaks(response) == []
    assert str(env.b.engagement_id) in response.text  # the control: other clients are unchanged


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac5_request_item_search_finds_nothing_of_the_walled_client(
    env: Env, role: str
) -> None:
    who = await env.walled(role)
    response = await env.get(who, "/v1/firm/search/request-items?q=Bank%20confirmation")
    assert response.status_code == 200, response.text
    assert env.leaks(response) == []
    assert str(env.b.item_id) in response.text


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac5_searching_for_the_walled_client_by_name_finds_nothing(
    env: Env, role: str
) -> None:
    who = await env.walled(role)
    for query in (env.a.marker, "walled"):  # its exact name, then a part of it
        response = await env.get(who, f"/v1/firm/search/request-items?q={query}")
        assert response.status_code == 200, response.text
        assert response.json() == []
        response = await env.get(who, f"/v1/firm/clients/search?q={query}")
        assert response.status_code in (200, 403), response.text
        assert env.leaks(response) == []
        if response.status_code == 200:
            assert response.json() == []


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac5_the_client_picker_hides_the_walled_client(env: Env, role: str) -> None:
    who = await env.walled(role)
    response = await env.get(who, "/v1/firm/clients/search?q=Client")
    assert response.status_code in (200, 403), response.text
    assert env.leaks(response) == []
    if response.status_code == 200:
        assert str(env.b.client_id) in response.text


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac5_the_waiting_counts_leave_out_the_walled_engagement(
    env: Env, role: str
) -> None:
    who = await env.walled(role)
    for path in (
        "/v1/firm/waiting/overdue",
        "/v1/firm/waiting/review",
        "/v1/firm/waiting/fieldwork",
    ):
        response = await env.get(who, path)
        assert response.status_code == 200, (path, response.text)
        assert env.leaks(response) == [], path
    overdue = await env.get(who, "/v1/firm/waiting/overdue")
    if role != "reviewer":  # the control: reviewers chase nothing; the rest count B's overdue item
        assert str(env.b.engagement_id) in overdue.text


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac5_the_findings_search_leaves_out_the_walled_client(
    env: Env, seed: Seeder, role: str
) -> None:
    for site in (env.a, env.b):
        await seed.run(
            "INSERT INTO findings (tenant_id, engagement_id, title, raised_by) "
            "VALUES ($1, $2, $3, $4)",
            env.tenant_id,
            site.engagement_id,
            f"Cut-off error {site.marker}",
            env.admin.user_id,
        )
    who = await env.walled(role)
    response = await env.get(who, "/v1/firm/search/findings?q=Cut-off")
    assert response.status_code == 200, response.text
    assert env.leaks(response) == []
    assert env.b.marker in response.text


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac5_notifications_about_the_walled_engagement_are_hidden(
    env: Env, seed: Seeder, role: str
) -> None:
    who = await env.walled(role)
    for site in (env.a, env.b):
        await seed.run(
            "INSERT INTO notifications (id, tenant_id, recipient_user_id, kind, event_id, "
            "engagement_id, subject_type, subject_id) "
            "VALUES ($1, $2, $3, 'evidence.uploaded', $4, $5, 'evidence_version', $6)",
            uuid.uuid4(),
            env.tenant_id,
            who.user_id,
            uuid.uuid4(),
            site.engagement_id,
            site.version_id,
        )
    response = await env.get(who, "/v1/notifications")
    assert response.status_code == 200, response.text
    assert env.leaks(response) == []
    assert str(env.b.engagement_id) in response.text
    assert cast(dict[str, object], response.json())["unread_count"] == 1


@pytest.mark.parametrize("role", STAFF_ROLES)
async def test_spec002_ac5_open_independence_requests_hide_the_walled_client(
    env: Env, seed: Seeder, role: str
) -> None:
    """A team member asked to confirm independence, then walled: the request names the client."""
    firm_role = None
    who = await seed.person(env.tenant_id, firm_role)
    for site in (env.a, env.b):
        await seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            env.tenant_id,
            site.engagement_id,
            who.user_id,
            role,
        )
        await seed.run(
            "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status) "
            "VALUES ($1, $2, $3, 'requested')",
            env.tenant_id,
            site.engagement_id,
            who.user_id,
        )
    await env.net.wall(env.admin, who, env.a)
    response = await env.get(who, "/v1/firm/confirmations")
    assert response.status_code == 200, response.text
    assert env.leaks(response) == []
    assert str(env.b.engagement_id) in response.text


# --- AC-4: and nothing is reached by id ----------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
async def test_spec002_ac4_the_walled_engagement_is_not_found_by_id(env: Env, role: str) -> None:
    who = await env.walled(role)
    for tail in ("", "/request-items", "/evidence-versions", "/team", "/setup", "/board-summary"):
        response = await env.get(who, f"/v1/engagements/{env.a.engagement_id}{tail}")
        assert response.status_code == 404, (tail, response.text)
        assert response.json() == {"detail": "not found"}
        control = await env.get(who, f"/v1/engagements/{env.b.engagement_id}{tail}")
        assert control.status_code == 200, (tail, control.text)
