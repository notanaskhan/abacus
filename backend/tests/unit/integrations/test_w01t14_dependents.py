"""W-01-T14 (red): a capability that requires an integration fails at admission with the
integration's code, and dependents come from the registered provider."""

from __future__ import annotations

from collections.abc import Sequence

from abacus.modules.integrations import dependents as dep


def test_ac_needs_reauth_fails_admission_with_integration_reauth_required() -> None:
    statuses = {"cch_axcess_tax": "needs_reauth", "google_workspace": "connected"}
    assert dep.admission_failure(["google_workspace", "cch_axcess_tax"], statuses) == (
        "cch_axcess_tax",
        "integration_reauth_required",
    )


def test_every_other_state_names_its_code_and_connected_admits() -> None:
    assert dep.admission_failure(["x"], {"x": "needs_attention"}) == ("x", "integration_unhealthy")
    for status in ("paused", "disconnected", "connecting"):
        assert dep.admission_failure(["x"], {"x": status}) == ("x", "integration_not_connected")
    assert dep.admission_failure(["x"], {}) == ("x", "integration_not_connected")
    assert dep.admission_failure(["x"], {"x": "connected"}) is None
    assert dep.admission_failure([], {}) is None


async def test_dependents_come_from_the_registered_provider() -> None:
    async def provider(key: str) -> Sequence[str]:
        return ["tax.season_progress_reporter"] if key == "cch_axcess_tax" else []

    dep.register_dependents_provider(provider)
    assert await dep.dependents_of("cch_axcess_tax") == ["tax.season_progress_reporter"]
    assert await dep.dependents_of("slack") == []
