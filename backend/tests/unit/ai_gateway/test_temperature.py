"""The gateway pins a sampling temperature per model where the model accepts one (founder,
2026-10-12): sent in the request body for those, never sent to models that reject it."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from abacus.ai_gateway.providers import ModelRequest
from abacus.ai_gateway.routes._anthropic import message_args
from abacus.kernel.config import CatalogModel


def _request(temperature: float | None) -> ModelRequest:
    return ModelRequest("claude-haiku-4-5-20251001", "system", "user", 100, "x@v1", temperature)


def test_a_pinned_temperature_is_sent_in_the_body() -> None:
    assert message_args(_request(0.0))["extra_body"] == {"temperature": 0.0}


def test_no_temperature_is_sent_to_a_model_without_one() -> None:
    assert "extra_body" not in message_args(_request(None))
    assert "temperature" not in message_args(_request(None))


def test_the_catalog_pins_it_per_model_and_bounds_it() -> None:
    base = {"name": "m", "ids": {"direct": "m-1"}, "usd_in": Decimal(1), "usd_out": Decimal(5)}
    assert CatalogModel.model_validate(base).temperature is None
    assert CatalogModel.model_validate({**base, "temperature": 0}).temperature == 0
    with pytest.raises(ValidationError):
        CatalogModel.model_validate({**base, "temperature": 1.5})
