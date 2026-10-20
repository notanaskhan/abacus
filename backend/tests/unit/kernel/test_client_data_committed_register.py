"""SPEC-036 AC-1, AC-8 (TASK-075) with the register as committed: it starts empty ("nothing opens
yet"), so `model_data_boundary: client_data` cannot be turned on in staging or production until
someone enters Bedrock's terms (ADR-114), and the default never lets a real model near a real firm.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from abacus.kernel.config import Settings

from .test_client_data_settings import (
    _catalog,  # pyright: ignore[reportPrivateUsage] -- shared setup
)
from .test_model_data_boundary_settings import (
    _environment,  # pyright: ignore[reportPrivateUsage] -- shared setup
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac1_client_data_cannot_be_turned_on_while_the_committed_register_is_empty(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    with pytest.raises(ValidationError, match="none covers today"):
        Settings(
            model_data_boundary="client_data",
            model_routes=("bedrock",),
            model_catalog=_catalog(),  # pyright: ignore[reportArgumentType] -- the validator
        )


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac1_the_default_boundary_is_synthetic_only_and_real_routes_are_refused(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _environment(monkeypatch, environment)
    assert Settings().model_data_boundary == "synthetic_only"
    with pytest.raises(ValidationError, match="evaluation environment only"):
        Settings(
            model_routes=("bedrock",),
            model_catalog=_catalog(),  # pyright: ignore[reportArgumentType] -- the validator
        )
