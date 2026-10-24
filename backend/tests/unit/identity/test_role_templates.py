"""G-01-T05 (AC5.1 to AC5.3): ADM-02b's role templates and capability grid.

- The generated module matches `docs/architecture/role-templates.yaml`.
- **Drift (AC5.2).** A `source: matrix` row is held to the compiled permission matrix: an `allow`
  cell must be granted (any non-deny cell) on every action to one of the template's roles, and a
  `deny` or `delegated` (D) cell must not be a plain `allow` for any of them. When a later epic
  changes an action a row names, this fails in that epic's change.
- **I-AGENT-NEVER (AC5.3).** The agent principal is denied every action in the rows from "Approve
  source document" to "Reveal masked TIN/SSN", and the agent row is locked.
"""

from __future__ import annotations

from typing import cast

import pytest

from abacus.modules.identity import _role_templates as generated
from abacus.modules.identity.authz._matrix import ACTIONS
from abacus_tools.codegen import role_templates as codegen

_ROWS = {str(row["key"]): row for row in generated.GRID}
_MATRIX_ROWS = sorted(
    key
    for key, row in _ROWS.items()
    if cast(list[str], row["actions"])
    and all(a in ACTIONS for a in cast(list[str], row["actions"]))
)
_NOT_GRANTED = frozenset({"deny"})


def _cell(action: str, role: str) -> str | None:
    return ACTIONS[action].get(role)


def test_the_generated_module_is_up_to_date() -> None:
    assert codegen.TARGET.read_text() == codegen.render(codegen.SOURCE.read_text())
    assert codegen.TS_TARGET.read_text() == codegen.render_ts(codegen.SOURCE.read_text())


def test_ac5_1_eight_templates_and_sixteen_rows_in_the_designs_order() -> None:
    assert tuple(generated.TEMPLATES) == codegen.TEMPLATES
    assert len(generated.GRID) == 16
    assert next(iter(_ROWS)) == "users_roles_offices" and list(_ROWS)[-1] == "reveal_tin"
    for row in generated.GRID:
        assert set(cast(dict[str, str], row["cells"])) == set(codegen.TEMPLATES)


def test_every_named_action_is_a_matrix_action_or_the_row_is_policy() -> None:
    for key, row in _ROWS.items():
        for action in cast(list[str], row["actions"]):
            assert action in ACTIONS, (key, action)  # a named action must exist


@pytest.mark.parametrize("key", _MATRIX_ROWS)
def test_ac5_2_matrix_rows_do_not_drift_from_the_matrix(key: str) -> None:
    row = _ROWS[key]
    actions = cast(list[str], row["actions"])
    for template, cell in cast(dict[str, str], row["cells"]).items():
        roles = cast(list[str], generated.TEMPLATES[template]["roles"])
        if cell == "allow":
            for action in actions:
                granted = [
                    r for r in roles if _cell(action, r) not in (None, *tuple(_NOT_GRANTED))
                ]
                assert granted, f"{key}: {template} is allowed but no role holds {action}"
        elif cell in ("deny", "delegated"):
            for action in actions:
                plain = [r for r in roles if _cell(action, r) == "allow"]
                assert not plain, f"{key}: {template} is {cell} but {plain} hold {action}"


def test_ac5_3_i_agent_never() -> None:
    assert set(generated.AGENT_NEVER) <= set(_ROWS)
    keys = list(_ROWS)
    span = keys[keys.index("approve_source_document") : keys.index("reveal_tin") + 1]
    assert list(generated.AGENT_NEVER) == span
    for key in span:
        for action in cast(list[str], _ROWS[key]["actions"]):
            assert _cell(action, "agent") in (None, "deny"), (key, action)
            assert _cell(action, "agent") != "task_scope", (key, action)


def test_the_compiler_refuses_an_unknown_cell() -> None:
    source = codegen.SOURCE.read_text().replace(
        "firm_admin: allow, it_security: conditional",
        "firm_admin: maybe, it_security: conditional",
        1,
    )
    with pytest.raises(ValueError, match="unknown cells"):
        codegen.render(source)
