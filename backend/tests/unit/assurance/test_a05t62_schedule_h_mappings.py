"""A-05-T62 close (S31; TASK-6228; DEC-2823): the Schedule H line mapping is published as firm
content: a dry run reports problems by code and place; only a person publishes, never a client,
an agent or support; a refused version writes nothing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.assurance import schedule_h_mappings as m
from abacus.modules.identity.api import Forbidden
from abacus.modules.identity.context import AuthContext


def _body(*rows: tuple[str, str]) -> m.MappingPublishIn:
    return m.MappingPublishIn(
        effective_plan_year=2025,
        rows=[m.MappingRowIn(fs_caption_key=c, schedule_h_line=line) for c, line in rows],
    )


def _ctx(kind: str = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # actor kind under test
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
        client=client,
    )


def test_problems_are_codes_and_places() -> None:
    body = _body(
        ("net_assets.receivable_employer", "1b(1)"),
        ("net_assets.receivable_employer", "1b(1)"),
        ("Net Assets", "1b-(2)"),
    )
    assert m.problems_of(body) == [
        "duplicate_caption@rows.1",
        "caption_key_invalid@rows.2",
        "schedule_h_line_invalid@rows.2",
    ]


@pytest.fixture
def allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ok(*_: object) -> None:
        return None

    monkeypatch.setattr(m, "authorise", ok)

    def no_writes(*_: object) -> object:
        raise AssertionError("nothing is written")

    monkeypatch.setattr(m, "uow", no_writes)


async def test_a_dry_run_validates_and_writes_nothing(allowed: None) -> None:
    out = await m.publish_mapping(_ctx(), _body(("net_assets.total", "1l")), dry_run=True)
    assert (out.status, out.version, out.problems) == ("validated", None, [])


async def test_a_version_with_problems_is_refused_and_writes_nothing(allowed: None) -> None:
    out = await m.publish_mapping(_ctx(), _body(("Bad Key", "1l")), dry_run=False)
    assert out.status == "refused" and out.problems == ["caption_key_invalid@rows.0"]


async def test_a_client_never_sees_it_and_an_agent_never_publishes(allowed: None) -> None:
    with pytest.raises(NotFound):
        await m.publish_mapping(_ctx(client=True), _body(("a", "1l")), dry_run=True)
    with pytest.raises(Forbidden):
        await m.publish_mapping(_ctx("agent"), _body(("a", "1l")), dry_run=False)


def test_publishing_needs_a_fresh_second_factor_and_no_agent() -> None:
    from abacus.modules.identity.authz import matrix

    entries = matrix.ACTIONS["ebp_schedule_h_mapping.publish"]
    assert entries["mfa_recent"] == "required"
    assert entries["agent"] == "deny" and entries["system"] == "deny"
