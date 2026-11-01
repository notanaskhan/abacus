"""A-03-T18 (TASK-2821; ADR-078, ADR-340 §5): the server-seed rule, tested independently of
A-03-T10's suite. The seed is the server's own 24 bits; only the scenario loader on a synthetic
firm passes one, inside the range. Removing the rule (taking a seed from anywhere, or from any
firm) fails here.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.sampling import sample_sets

TENANT = TenantContext(UUID(int=1), "human", "a03t18")


def _synthetic(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    async def is_synthetic_firm(_tenant: object) -> bool:
        return value

    monkeypatch.setattr(sample_sets, "is_synthetic_firm", is_synthetic_firm)


async def test_without_a_scenario_seed_the_server_draws_24_bits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _synthetic(monkeypatch, True)
    seeds = {await sample_sets._seed(TENANT, None) for _ in range(8)}  # pyright: ignore[reportPrivateUsage] -- the rule under test
    assert {source for _, source in seeds} == {"server"}
    assert all(0 <= seed < 2**24 for seed, _ in seeds)
    assert len(seeds) > 1  # drawn, never a constant


async def test_a_real_firm_never_takes_a_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    _synthetic(monkeypatch, False)
    with pytest.raises(sample_sets.SeedNotAllowed):
        await sample_sets._seed(TENANT, 6171281)  # pyright: ignore[reportPrivateUsage] -- as above


@pytest.mark.parametrize("seed", [-1, 2**24])
async def test_a_seed_outside_24_bits_is_refused_even_on_a_synthetic_firm(
    monkeypatch: pytest.MonkeyPatch, seed: int
) -> None:
    _synthetic(monkeypatch, True)
    with pytest.raises(sample_sets.SeedNotAllowed):
        await sample_sets._seed(TENANT, seed)  # pyright: ignore[reportPrivateUsage] -- as above


async def test_the_scenario_loader_seeds_a_synthetic_firm(monkeypatch: pytest.MonkeyPatch) -> None:
    _synthetic(monkeypatch, True)
    assert await sample_sets._seed(TENANT, 6171281) == (6171281, "scenario")  # pyright: ignore[reportPrivateUsage] -- as above


def test_the_seed_refusal_is_403_seed_not_allowed() -> None:
    assert sample_sets.SeedNotAllowed.code == "seed_not_allowed"
    assert sample_sets.SEED_BITS == 24
