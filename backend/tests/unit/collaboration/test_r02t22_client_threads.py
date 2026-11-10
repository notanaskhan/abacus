"""R-02-T22 (SPEC-646 AC-31 to AC-34): the client comment path's rules, as code.

The HTTP path (Dana's page comment reaching the firm, Victoria's private question) is the
integration suite's; here: the author-only locator, the client text rule, the policy registry, and
the portal anchors' registration."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.collaboration import client_threads as ct
from abacus.modules.collaboration.errors import CommentTooLong, EmptyComment


def _ctx(client: bool = True, kind: str = "human") -> SimpleNamespace:
    return SimpleNamespace(
        user_id=uuid4(),
        client=object() if client else None,
        tenant=SimpleNamespace(actor_kind=kind),
    )


def test_ac33_an_author_only_anchor_scopes_each_thread_to_its_author() -> None:
    ct.register_client_policy("test_letter", "author_only")
    victoria, robert = _ctx(), _ctx()
    mine = ct._scoped(victoria, "test_letter", None)  # pyright: ignore[reportPrivateUsage, reportArgumentType] -- the cleaning rule under test
    theirs = ct._scoped(robert, "test_letter", None)  # pyright: ignore[reportPrivateUsage, reportArgumentType] -- the cleaning rule under test
    assert mine == {"author": str(victoria.user_id)}
    assert mine != theirs


def test_anchor_readers_is_the_default_and_keeps_the_locator() -> None:
    assert ct.policy_of("never_registered") == "anchor_readers"
    ctx = _ctx()
    assert ct._scoped(ctx, "never_registered", {"page": 2}) == {"page": 2}  # pyright: ignore[reportPrivateUsage, reportArgumentType] -- the cleaning rule under test


def test_a_policy_is_registered_once() -> None:
    ct.register_client_policy("test_once", "author_only")
    ct.register_client_policy("test_once", "author_only")
    with pytest.raises(RuntimeError):
        ct.register_client_policy("test_once", "anchor_readers")


def test_ac34_client_text_is_plain_and_bounded() -> None:
    assert ct._clean("  Can the note say both?\u202e ") == "Can the note say both?"  # pyright: ignore[reportPrivateUsage] -- the cleaning rule under test
    with pytest.raises(EmptyComment):
        ct._clean("   ")  # pyright: ignore[reportPrivateUsage]  # the cleaning rule under test
    with pytest.raises(CommentTooLong):
        ct._clean("x" * (ct.MAX_CLIENT_BODY + 1))  # pyright: ignore[reportPrivateUsage] -- the cleaning rule under test


def test_only_a_client_person_takes_the_client_path() -> None:
    for ctx in (_ctx(client=False), _ctx(kind="agent"), _ctx(kind="system")):
        with pytest.raises(Exception, match="role"):
            ct._client(ctx)  # pyright: ignore[reportPrivateUsage, reportArgumentType]  # the cleaning rule under test


def test_the_portal_registers_its_three_anchors() -> None:
    import abacus.modules.portal.api as portal_api  # registers at import

    assert portal_api.ROUTERS
    from abacus.modules.collaboration.api import registered_kinds

    assert {"client_approval_item", "deliverable_version", "governance_communication"} <= set(
        registered_kinds()
    )
    assert ct.policy_of("governance_communication") == "author_only"
