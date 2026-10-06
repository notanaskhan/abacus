"""AC-20: structlog JSON logging that refuses Restricted data (ADR-022, ADR-031)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Annotated

import pytest
from pydantic import BaseModel

from abacus.kernel.classification import classified
from abacus.kernel.logging import get_logger


class Firm(BaseModel):
    id: Annotated[uuid.UUID, classified("confidential")]
    name: Annotated[str, classified("confidential")]
    region: Annotated[str, classified("public")]


class Client(BaseModel):
    id: Annotated[uuid.UUID, classified("confidential")]
    balance: Annotated[str, classified("restricted")]


class Wrapper(BaseModel):
    firm: Annotated[Firm, classified("confidential")]
    client: Annotated[Client, classified("confidential")]


def _events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    captured = capsys.readouterr()
    lines = [line for line in (captured.out + captured.err).splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_ac20_emits_one_json_object_with_event_level_timestamp_and_kwargs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    get_logger("test").info("thing_happened", count=3, ok=True, label="x")
    (event,) = _events(capsys)
    assert event["event"] == "thing_happened"
    assert event["level"] == "info"
    assert isinstance(event["timestamp"], str)
    assert event["timestamp"]
    assert event["count"] == 3
    assert event["ok"] is True
    assert event["label"] == "x"


@pytest.mark.parametrize("level", ["debug", "info", "warning", "error"])
def test_ac20_level_reflects_the_method_used(
    capsys: pytest.CaptureFixture[str], level: str
) -> None:
    log = get_logger("test")
    getattr(log, level)("evt")
    events = _events(capsys)
    assert [e["level"] for e in events][-1:] == [level]


def test_ac20_each_call_is_its_own_line(capsys: pytest.CaptureFixture[str]) -> None:
    log = get_logger("test")
    log.info("one")
    log.info("two")
    assert [e["event"] for e in _events(capsys)] == ["one", "two"]


def test_ac20_uuid_and_date_values_are_serialised(capsys: pytest.CaptureFixture[str]) -> None:
    ident = uuid.uuid4()
    get_logger("test").info("evt", id=ident, day=date(2026, 10, 6))
    (event,) = _events(capsys)
    assert event["id"] == str(ident)
    assert event["day"] == "2026-10-06"


def test_ac20_classified_model_without_restricted_fields_is_logged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    firm = Firm(id=uuid.uuid4(), name="Acme LLP", region="US")
    get_logger("test").info("evt", firm=firm)
    (event,) = _events(capsys)
    assert event["firm"] == {"id": str(firm.id), "name": "Acme LLP", "region": "US"}


def test_ac20_model_with_a_restricted_field_raises_and_logs_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = Client(id=uuid.uuid4(), balance="1234567.89")
    with pytest.raises(ValueError):
        get_logger("test").info("evt", client=client)
    assert _events(capsys) == []


def test_ac20_restricted_value_never_reaches_output_via_a_nested_model(
    capsys: pytest.CaptureFixture[str],
) -> None:
    wrapper = Wrapper(
        firm=Firm(id=uuid.uuid4(), name="Acme", region="US"),
        client=Client(id=uuid.uuid4(), balance="987654.32"),
    )
    with pytest.raises(ValueError):
        get_logger("test").info("evt", wrapper=wrapper)
    captured = capsys.readouterr()
    assert "987654.32" not in captured.out + captured.err


class Opaque:
    def __repr__(self) -> str:
        return "OPAQUE-REPR"


@pytest.mark.parametrize("value", [Opaque(), object(), {1, 2}, lambda: None])
def test_ac20_arbitrary_objects_are_refused(
    capsys: pytest.CaptureFixture[str], value: object
) -> None:
    with pytest.raises(ValueError):
        get_logger("test").info("evt", thing=value)
    assert "OPAQUE-REPR" not in capsys.readouterr().out
