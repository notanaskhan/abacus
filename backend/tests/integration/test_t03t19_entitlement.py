"""T-03-T19 (TASK-3338; DEC-2329): the retired flags' routes stand behind the entitlement.

Row acceptance: "the retired flags are gone from feature-flags.yaml with _flags.py regenerated, and
a firm without the tax entitlement still gets 404 on /tax-returns and the K-1 routes."
"""

from __future__ import annotations

from abacus.kernel import _flags
from abacus.kernel.clock import frozen

from . import test_t02t09_practice_board as t02t09
from .test_t02t09_practice_board import DEMO, Board

_as = t02t09._as  # pyright: ignore[reportPrivateUsage] -- T-02-T09's HTTP helper
engines = t02t09.engines
seed = t02t09.seed
board = t02t09.board


def test_ac_the_retired_flags_are_gone() -> None:
    registered = set(_flags.__dict__)
    assert not {"TAX_RETURNS_V1", "TAX_K1_RELEASE", "QUESTIONNAIRES_V1"} & registered


async def test_ac_a_firm_without_the_entitlement_gets_404(board: Board) -> None:
    await board.seed.run(
        "DELETE FROM tenant_entitlements WHERE tenant_id = $1 AND module = 'tax_returns'",
        board.tenant,
    )
    item = board.returns["Feld Household 1040"]
    with frozen(DEMO):
        call = _as(await board.person("Samuel Ito", None))
        for path in ("/v1/tax-returns", f"/v1/tax-returns/{item}/k1-packages"):
            found = await call("GET", path, params={"tax_year": 2025})
            assert found.status_code == 404, f"{path}: {found.text}"


async def test_ac_with_the_entitlement_the_board_answers(board: Board) -> None:
    with frozen(DEMO):
        call = _as(await board.person("Samuel Ito", None))
        found = await call("GET", "/v1/tax-returns", params={"tax_year": 2025})
    assert found.status_code == 200, found.text
