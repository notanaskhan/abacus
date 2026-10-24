"""Q-02-T37 (Q-02 AC-42): the fresh-MFA lint fails when a listed action loses `mfa_recent:
required`, leaves the matrix, is listed twice or sits in an unknown group; it passes on the
repository's own register and matrix."""

from __future__ import annotations

from abacus_tools.codegen.permission_matrix import source
from abacus_tools.quality.fresh_mfa import REGISTER, problems

MATRIX = """
actions:
  wall.create: {firm_admin: allow, mfa_recent: required}
  wall.remove: {firm_admin: allow}
"""


def _register(*entries: tuple[str, str]) -> str:
    lines = "".join(f"  - action: {a}\n    group: {g}\n" for a, g in entries)
    return f"actions:\n{lines}"


def test_the_repository_register_and_matrix_pass() -> None:
    assert problems(REGISTER.read_text(encoding="utf-8"), source()) == []


def test_removing_mfa_recent_from_a_listed_action_fails() -> None:
    found = problems(_register(("wall.create", "wall"), ("wall.remove", "wall")), MATRIX)
    assert found == ["wall.remove: listed as fresh-MFA but lacks `mfa_recent: required`"]


def test_a_listed_action_missing_from_the_matrix_fails() -> None:
    assert problems(_register(("wall.approve", "wall")), MATRIX) == [
        "wall.approve: not in the permission matrix"
    ]


def test_a_duplicate_or_an_unknown_group_fails() -> None:
    found = problems(_register(("wall.create", "wall"), ("wall.create", "misc")), MATRIX)
    assert found == ["wall.create: listed twice", "wall.create: unknown group 'misc'"]


def test_an_empty_register_fails() -> None:
    assert problems("actions: []\n", MATRIX) == ["the fresh-MFA register lists no actions"]
