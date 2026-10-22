"""Q-02-T13: the generated security tests are current, and a hand edit to either fails
`make check-generated` (the generator's `--check`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.codegen import security_tests as gen


def test_the_generated_files_are_current() -> None:
    assert gen.main(["--check"]) == 0


@pytest.mark.parametrize("target", ["ISOLATION", "MATRIX", "INTROSPECTION"])
def test_a_hand_edit_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    for name in ("ISOLATION", "MATRIX", "INTROSPECTION"):
        copy = tmp_path / f"{name}.py"
        copy.write_text(getattr(gen, name).read_text())
        monkeypatch.setattr(gen, name, copy)
    edited: Path = getattr(gen, target)
    edited.write_text(edited.read_text().replace('"deny"', '"allow"', 1).replace('"', "'", 1))
    assert gen.main(["--check"]) == 1


def test_every_matrix_allow_with_a_condition_is_expected_to_deny() -> None:
    from abacus.modules.identity.api import RULES

    for action, rule in RULES.items():
        if rule.level_in or rule.gates_met or rule.attest_client is not None:
            assert all(gen.expected(rule, role) == "deny" for role in gen.HUMAN_ROLES), action
