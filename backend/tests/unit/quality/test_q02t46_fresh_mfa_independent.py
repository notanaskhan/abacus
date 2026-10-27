# ac-test-author: ayushkbhatia
"""Q-02-T46 (TASK-1455): independent AC tests (ADR-078) for the fresh-MFA lint, Q-02 AC-42
(SPEC-341 story 11; DEC-330).

AC-42: given `docs/architecture/fresh-mfa-actions.yaml`, when any listed action lacks
`mfa_recent: required` in the permission matrix, then CI fails. The register covers the AC's
groups (lifting a wall, AI policy, exports, legal holds, the independence conclusion, the
data-boundary opt-in, TIN reveal, incident decisions).

Boundary: the lint's public entry points, `abacus_tools.quality.fresh_mfa.problems` and `main()`
(its exit code is what `make check-fast` acts on), over the real register and matrix sources and
over copies of the matrix sources in a temporary directory with one condition removed (the
seeded violations; no tracked file is touched). The matrix sources are read through
`abacus_tools.codegen.permission_matrix.source(directory)`, the lint's own reader.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Final, cast

import pytest
import yaml

from abacus_tools.codegen import permission_matrix
from abacus_tools.quality import fresh_mfa

REPO: Final = Path(__file__).resolve().parents[4]
REGISTER: Final = REPO / "docs" / "architecture" / "fresh-mfa-actions.yaml"
MATRIX: Final = REPO / "docs" / "architecture" / "permission-matrix"
# AC-42's groups and the actions Q-02 itself adds (firm export, holds, the opt-in).
AC42_GROUPS: Final = frozenset(
    {"wall", "ai_policy", "export", "legal_hold", "independence", "data_boundary", "reveal"}
    | {"incident"}
)
Q02_ACTIONS: Final = (
    "firm_export.request",
    "firm_export.approve",
    "firm_export.download",
    "legal_hold.place",
    "legal_hold.lift",
    "firm.ai_client_data",
    "tin.reveal",
    "wall.remove",
    "incident.decide",
)


def _listed() -> list[dict[str, str]]:
    data = cast(dict[str, object], yaml.safe_load(REGISTER.read_text(encoding="utf-8")))
    return cast(list[dict[str, str]], data["actions"])


def _seeded_matrix(tmp_path: Path, action: str) -> Path:
    """A copy of the matrix sources with `mfa_recent: required` removed from `action`'s row."""
    folder = tmp_path / "permission-matrix"
    shutil.copytree(MATRIX, folder)
    pattern = re.compile(rf"^(\s+{re.escape(action)}:\s*\{{.*?),\s*mfa_recent:\s*required", re.M)
    changed = 0
    for path in folder.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        seeded, n = pattern.subn(r"\1", text)
        if n:
            path.write_text(seeded, encoding="utf-8")
            changed += n
    assert changed == 1, f"{action}: its matrix row was not found to seed"
    return folder


def test_ac42_the_register_covers_every_group_the_ac_names() -> None:
    listed = _listed()
    assert {e["group"] for e in listed} >= AC42_GROUPS
    actions = {e["action"] for e in listed}
    missing = [a for a in Q02_ACTIONS if a not in actions]
    assert missing == []


def test_ac42_on_main_every_listed_action_requires_a_fresh_factor() -> None:
    register = REGISTER.read_text(encoding="utf-8")
    assert fresh_mfa.problems(register, permission_matrix.source()) == []
    assert fresh_mfa.main() == 0


@pytest.mark.parametrize("action", Q02_ACTIONS)
def test_seeded_removing_mfa_recent_from_a_listed_action_fails_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    seeded = permission_matrix.source(_seeded_matrix(tmp_path, action))
    found = fresh_mfa.problems(REGISTER.read_text(encoding="utf-8"), seeded)
    assert any(action in problem for problem in found), found
    # The CI step: the lint's exit code on the seeded sources.
    monkeypatch.setattr(fresh_mfa, "source", lambda: seeded)
    assert fresh_mfa.main() == 1


def test_seeded_a_listed_action_missing_from_the_matrix_fails_ci(tmp_path: Path) -> None:
    register = tmp_path / "fresh-mfa-actions.yaml"
    entries = [*_listed(), {"action": "firm_export.unknown_probe", "group": "export"}]
    register.write_text(yaml.safe_dump({"actions": entries}), encoding="utf-8")
    found = fresh_mfa.problems(register.read_text(encoding="utf-8"), permission_matrix.source())
    assert any("firm_export.unknown_probe" in problem for problem in found), found


def test_seeded_an_empty_register_fails_ci() -> None:
    assert fresh_mfa.problems("actions: []\n", permission_matrix.source())
