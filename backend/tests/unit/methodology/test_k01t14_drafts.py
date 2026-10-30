"""K-01-T14 (TASK-2315; K-01 §3.5; DEC-1361): the draft change list is computed by code against
`drafted_from` by step key, numbering alone is no change, a new step's key is stable and valid,
and the mandatory lock refuses anyone but a person holding `methodology.approve`."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden, Resource
from abacus.modules.methodology import drafts


def _step(key: str, **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "step_key": key,
        "text": f"Step {key}",
        "assertions": [],
        "standard_refs": [],
        "level": "planning",
        "guidance": None,
        "mandatory": False,
        "lock_note": None,
    }
    return {**base, **over}


def test_ac5_2_the_change_list_is_by_key_and_names_the_fields() -> None:
    before = [_step("a"), _step("b"), _step("c", mandatory=True), _step("d")]
    after = [
        _step("a"),
        _step("b", text="Step b, tailored"),
        _step("c", mandatory=False),
        _step("e"),
    ]
    changes, unchanged = drafts.diff_steps(before, after)
    assert unchanged == 1
    assert changes == (
        drafts.StepChange("b", "changed", ("text",)),
        drafts.StepChange("c", "changed", ("mandatory",)),
        drafts.StepChange("d", "removed"),
        drafts.StepChange("e", "added"),
    )


def test_numbering_alone_is_not_a_change() -> None:
    before = [{**_step("a"), "number": 1}]
    after = [{**_step("a"), "number": 2}]
    assert drafts.diff_steps(before, after) == ((), 1)


def test_a_new_steps_key_is_valid_and_unique() -> None:
    keys = {drafts._new_key("BH-EBP-110") for _ in range(50)}  # pyright: ignore[reportPrivateUsage] -- the key format is the column's CHECK
    assert len(keys) == 50
    for key in keys:
        assert re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,79}", key), key
        assert key.startswith("bh-ebp-110-m")


def _ctx(kind: str = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # each actor kind
        user,
        uuid.uuid4(),
        "firm_admin",
        datetime.now(UTC),
        client=client,
    )


@pytest.fixture
def kept(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The refusals `mandatory_guard` records (its own unit of work in the service)."""
    out: list[str] = []

    async def record(ctx: AuthContext, version_id: UUID, action: str) -> None:
        out.append(action)

    monkeypatch.setattr(drafts, "record_refusal", record)
    return out


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac5_3_the_agent_and_the_system_never_lock(kind: str, kept: list[str]) -> None:
    with pytest.raises(Forbidden):
        await drafts.mandatory_guard(_ctx(kind), uuid.uuid4())
    assert kept == ["decision.refused_non_human"]


async def test_ac5_3_a_person_without_approve_is_refused_and_audited(
    monkeypatch: pytest.MonkeyPatch, kept: list[str]
) -> None:
    async def authorise(ctx: AuthContext, action: str, resource: Resource) -> None:
        raise Forbidden(action, "role")

    monkeypatch.setattr(drafts, "authorise", authorise)
    with pytest.raises(Forbidden):
        await drafts.mandatory_guard(_ctx(), uuid.uuid4())
    assert kept == ["methodology_step.mandatory_refused"]


async def test_a_client_principal_sees_no_methodology(kept: list[str]) -> None:
    with pytest.raises(NotFound):
        await drafts.mandatory_guard(_ctx(client=True), uuid.uuid4())
    assert kept == []
