"""Q-02 AC-21 (Q-02-T32; ADR-167 §1, ADR-031): a tagged value never reaches a log line, a Sentry
event or a metric attribute. One of each is seeded from a model holding a `pii_kind="tin"` value.

The model itself is refused by the logger (it has Restricted fields); its value copied out into a
plain string, the way a careless call site would, is masked by the TIN backstop in all three.
The seeded TIN is a 9xx ITIN-shaped value built at run time (ADR-085).
"""

from __future__ import annotations

import json
from typing import Annotated, cast

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from pydantic import BaseModel
from sentry_sdk.types import Event

from abacus.kernel.classification import classified, mask, pii_paths
from abacus.kernel.error_tracking import scrub
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import ScrubbingMeter
from abacus.kernel.tin_patterns import find_tins

DIGITS = "9" + "00" + "70" + "1234"  # a 9xx ITIN form: passes the ITIN rules, never an SSN
TIN = f"{DIGITS[:3]}-{DIGITS[3:5]}-{DIGITS[5:]}"


class Taxpayer(BaseModel):
    name: Annotated[str, classified("confidential")]
    tin: Annotated[str, classified("restricted", pii_kind="tin")]


def _taxpayer() -> Taxpayer:
    return Taxpayer(name="Brightwater Hale", tin=TIN)


def _leaks(text: str) -> bool:
    return TIN in text or DIGITS in text or bool(find_tins(text))


def _lines(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


def test_ac21_the_seeded_model_is_tagged() -> None:
    assert pii_paths(Taxpayer, "tin") == ("tin",)


def test_ac21_a_log_line_given_the_model_is_refused_and_nothing_is_written(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError, match="tin") as refused:
        get_logger("test").info("taxpayer.loaded", taxpayer=_taxpayer())
    assert not _leaks(str(refused.value))
    assert not _leaks(_lines(capsys))


def test_ac21_a_log_line_given_the_value_masks_it(capsys: pytest.CaptureFixture[str]) -> None:
    value = _taxpayer().tin
    get_logger("test").info(
        "taxpayer.loaded", tin=value, note=f"id {value} on file", values=[value, "ok"]
    )
    out = _lines(capsys)
    assert not _leaks(out)
    [event] = [json.loads(line) for line in out.splitlines() if line.strip()]
    assert event["tin"] == mask(TIN, "tin")
    assert event["note"] == f"id {mask(TIN, 'tin')} on file"
    assert event["values"] == [mask(TIN, "tin"), "ok"]


def test_ac21_a_sentry_event_built_from_the_model_keeps_nothing_of_the_value() -> None:
    taxpayer = _taxpayer()
    dumped = taxpayer.model_dump()
    event = cast(
        Event,
        {
            "event_id": "e1",
            "level": "error",
            "environment": "test",
            "message": f"failed for {taxpayer.tin}",
            "extra": dumped,
            "request": {"data": dumped},
            "tags": {"route": f"/v1/x/{taxpayer.tin}", "tenant_id": taxpayer.tin},
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": f"bad tin {taxpayer.tin}",
                        "module": "abacus.x",
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "abacus.x",
                                    "function": f"load_{DIGITS}",
                                    "lineno": 3,
                                    "filename": f"/srv/app/{TIN}.py",
                                    "vars": dumped,
                                }
                            ]
                        },
                    }
                ]
            },
        },
    )
    kept = scrub(event)
    assert kept is not None
    assert not _leaks(json.dumps(kept))
    assert cast(dict[str, dict[str, str]], kept)["tags"]["tenant_id"] == mask(TIN, "tin")


def test_ac21_a_metric_attribute_built_from_the_model_is_masked() -> None:
    found = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[found])
    try:
        scrubbing = ScrubbingMeter(provider.get_meter("test"))
        taxpayer = _taxpayer()
        scrubbing.create_counter("abacus.test_pii").add(
            1, {"reason": taxpayer.tin, "outcome": "ok"}
        )
        scrubbing.create_histogram("abacus.test_pii_hist").record(
            2.0, {"reason": f"tin {taxpayer.tin}"}
        )
        data = found.get_metrics_data()
        assert data is not None
        assert not _leaks(data.to_json())
        attributes = [
            dict(point.attributes or {})
            for resource in data.resource_metrics
            for scope in resource.scope_metrics
            for metric in scope.metrics
            for point in metric.data.data_points
        ]
        assert {"reason": mask(TIN, "tin"), "outcome": "ok"} in attributes
        assert {"reason": f"tin {mask(TIN, 'tin')}"} in attributes
    finally:
        provider.shutdown()


def test_ac21_metric_attributes_without_a_tin_are_unchanged() -> None:
    found = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[found])
    try:
        ScrubbingMeter(provider.get_meter("test")).create_counter("abacus.test_plain").add(
            3, {"reason": "pii_in_context", "outcome": "refused", "work_class": 1}
        )
        data = found.get_metrics_data()
        assert data is not None
        [point] = [
            p
            for r in data.resource_metrics
            for s in r.scope_metrics
            for m in s.metrics
            for p in m.data.data_points
        ]
        assert dict(point.attributes or {}) == {
            "reason": "pii_in_context",
            "outcome": "refused",
            "work_class": 1,
        }
    finally:
        provider.shutdown()
