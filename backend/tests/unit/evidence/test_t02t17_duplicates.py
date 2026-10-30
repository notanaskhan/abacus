"""T-02-T17 (TASK-2325; DEC-58 g; DEC-1371): duplicates are accepted only for a client person's own
upload with `evidence.duplicate_review` on; a firm upload (or one on the client's behalf) keeps the
409; and the resolution is a person's (the agent, the system and a client principal are
refused)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.evidence import duplicates
from abacus.modules.identity.api import AuthContext, Forbidden


def _ctx(kind: str = "human", *, client: bool = False) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type]  # each actor kind
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
        client=client,
    )


@pytest.fixture
def flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(duplicates, "flag_enabled", on)


@pytest.mark.parametrize(
    ("client", "on_behalf", "accepted"),
    [(True, False, True), (True, True, False), (False, False, False)],
)
async def test_only_a_client_persons_own_upload_is_accepted(
    flag_on: None, client: bool, on_behalf: bool, accepted: bool
) -> None:
    assert await duplicates.accepts_duplicates(_ctx(client=client), on_behalf) is accepted


async def test_flag_off_keeps_the_409(monkeypatch: pytest.MonkeyPatch) -> None:
    async def off(_tenant: object, _flag: object) -> bool:
        return False

    monkeypatch.setattr(duplicates, "flag_enabled", off)
    assert await duplicates.accepts_duplicates(_ctx(client=True), False) is False


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_only_a_person_resolves(kind: str) -> None:
    with pytest.raises(Forbidden):
        await duplicates.resolve(
            _ctx(kind), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "keep_newer"
        )


async def test_a_client_principal_never_resolves() -> None:
    with pytest.raises(NotFound):
        await duplicates.resolve(
            _ctx(client=True), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "discard_duplicate"
        )
