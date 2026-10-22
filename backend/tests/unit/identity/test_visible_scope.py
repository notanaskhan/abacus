"""F-03-T27 (ADR-145): `visible_scope` builds the right filter for each scope kind and fails
closed without its lookup. The database property test is in
tests/integration/test_visible_scope_kinds.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Uuid, column

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.api import AuthContext, visible_scope


def _ctx(firm_role: str | None = None) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        firm_role,  # type: ignore[arg-type]  # a literal firm role or None
        datetime.now(UTC),
    )


def _sql(expression: object) -> str:
    return str(expression.compile(compile_kwargs={"literal_binds": False}))  # type: ignore[attr-defined]  # a SQL expression


ACTION = "engagement.read_metadata"


def test_engagement_and_work_item_read_through_visible() -> None:
    for kind in ("engagement", "work_item"):
        sql = _sql(visible_scope(_ctx(), ACTION, kind, column("engagement_id", Uuid())))
        assert "engagement_members" in sql
        assert "ethical_walls" in sql


def test_client_kinds_go_through_engagements_and_walls_on_the_client() -> None:
    for kind in ("client", "client_entity"):
        sql = _sql(visible_scope(_ctx(), ACTION, kind, column("client_id", Uuid())))
        assert "client_id IN" in sql
        assert "ethical_walls.client_id = client_id" in sql


def test_a_firm_role_that_allows_reads_every_unwalled_client() -> None:
    sql = _sql(visible_scope(_ctx("firm_admin"), ACTION, "client", column("client_id", Uuid())))
    assert "engagement" not in sql
    assert "ethical_walls" in sql


def test_client_kinds_fail_closed_without_the_engagements_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authz, "_clients_of_engagements", None)
    sql = _sql(visible_scope(_ctx(), ACTION, "client", column("client_id", Uuid())))
    assert sql == "false"


def test_a_portal_scope_matches_the_persons_grants_of_that_kind() -> None:
    expression = visible_scope(
        _ctx(), ACTION, "portal_scope", column("id", Uuid()), grant_kind="work_item"
    )
    sql = _sql(expression)
    assert "client_access_grants" in sql
    assert "work_item" in str(expression.compile().params.values())


def test_a_portal_scope_without_its_grant_kind_admits_nothing() -> None:
    sql = _sql(visible_scope(_ctx(), ACTION, "portal_scope", column("id", Uuid())))
    assert sql == "false"


def test_an_unknown_kind_is_an_error() -> None:
    with pytest.raises(ValueError, match="unknown scope kind"):
        visible_scope(_ctx(), ACTION, "galaxy", column("id", Uuid()))  # type: ignore[arg-type]  # the point
