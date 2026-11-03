"""A-04-T43 (TASK-3007; DEC-2057): `assurance/gates.py` registers G4 over A-04-T18's facts.

Row acceptance: "Northwind's G4 reads met after the 4:40 PM decision and reopens with
register_changed_after_approval after an edit to R4, and an amber PR cannot change gates.py." The
facts themselves are A-04-T18's integration test; here: the provider is the one registered, it is
the facts function, and the file is a named red file.
"""

from __future__ import annotations

from pathlib import Path

from abacus.modules.assurance import api as assurance_api  # registers the providers
from abacus.modules.assurance.planning_gate import g4_facts
from abacus.modules.engagements import slots

REPO = Path(__file__).resolve().parents[4]


def test_ac_g4_is_registered_from_gates_py_over_g4_facts() -> None:
    assert assurance_api.g4_facts is g4_facts
    assert slots._GATES["G4"] is g4_facts  # pyright: ignore[reportPrivateUsage]


def test_ac_gates_py_is_a_named_red_file() -> None:
    text = (REPO / "docs" / "architecture" / "protected-paths.md").read_text(encoding="utf-8")
    assert "backend/src/abacus/modules/assurance/gates.py" in text
