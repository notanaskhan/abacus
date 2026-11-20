"""T-08-T13 (TASK-8837; TAX-10, TAX-14; DEC-5839): review_checklist payload v2.

Row acceptance: "1065 Review Checklist v4 imports with 42 bound or manual items, an unknown check
code is a row problem, and v1 payloads still read."
"""

from __future__ import annotations

import pytest

from abacus.modules.methodology import check_codes
from abacus.modules.methodology.standards import PayloadInvalid, validate_payload


def _items(n: int, bound: int, code: str = "k1_sum_k") -> list[dict[str, object]]:
    return [
        {"key": f"i{i}", "section": "Schedule K", "text": f"Check {i}",
         **({"check_code": code} if i < bound else {})}
        for i in range(n)
    ]  # fmt: skip


def _payload(items: list[dict[str, object]], **extra: object) -> dict[str, object]:
    return {
        "kind": "review_checklist",
        "applies_to": {"form": "1065", "tax_year": 2025},
        "items": items,
        **extra,
    }


def test_ac_v4_with_42_bound_or_manual_items() -> None:
    check_codes.register_check_code("k1_sum_k", "Σ K-1 = Schedule K")
    payload = validate_payload(
        "review_checklist", _payload(_items(42, 30), two_year_threshold_pct="10")
    )
    assert check_codes.bound_count(payload) == (30, 12)


def test_ac_unknown_check_code_is_a_problem() -> None:
    payload = _payload(_items(3, 1, code="no_such_check"))
    assert check_codes.unknown_items(payload) == [0]
    with pytest.raises(PayloadInvalid):
        validate_payload("review_checklist", payload)


def test_ac_v1_payload_still_reads() -> None:
    v1 = _payload([{"key": "a", "section": "Page 1", "text": "Sign"}])
    out = validate_payload("review_checklist", v1)
    assert out["items"][0]["check_code"] is None  # type: ignore[index] -- the stored shape
    assert out["two_year_threshold_pct"] is None


def test_import_route_names_the_row() -> None:
    import inspect

    from abacus.modules.methodology import standards_routes

    assert '"check_code_unknown"' in inspect.getsource(standards_routes.import_standard_route)
