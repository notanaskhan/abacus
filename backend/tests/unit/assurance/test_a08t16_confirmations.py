"""A-08-T16 (TASK-8084; SPEC-657 F6): the confirmations core's rules. Row acceptance: "Tiles sum to
4, coverage computes 15.3%, and sending to a client-only address is refused with 409
address_not_verified." Tiles and the 409 against Postgres are `tests/integration` (end pass)."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.assurance.confirmations_service import (
    _INDEPENDENT,  # pyright: ignore[reportPrivateUsage] -- the rule under test
    AddressNotVerified,
    coverage_of,
)


def test_ac_coverage_is_15_3_percent() -> None:
    c = coverage_of(
        Decimal("5860000.00"),
        Decimal("897950.00"),
        Decimal("695200.00"),
        Decimal("4300.00"),
        Decimal("7750"),
    )
    assert c.sent_pct == Decimal("15.3")
    assert (c.confirmed_total, c.differences_total) == (Decimal("695200.00"), Decimal("4300.00"))


def test_a_client_supplied_address_is_never_independent() -> None:
    assert "client_supplied" not in _INDEPENDENT
    assert {"prior_year", "website", "phone", "public_register", "bank_published"} == set(
        _INDEPENDENT
    )
    assert AddressNotVerified.code == "address_not_verified"
