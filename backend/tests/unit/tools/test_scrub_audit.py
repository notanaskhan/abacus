"""Q-03-T083 (ADR-031, ADR-167): the pre-shadow scrubbing audit's scan, verdict and sink readers.

The acceptance: no Restricted value appears in any sampled sink, and each miss found becomes a test
in `test_classification_scrubbing.py`. These tests pin the audit itself: a seeded value is found as
written and as bare digits, a valid TIN the seed did not plant is found too, a masked form is not a
finding, a sink that never received the run marker makes the run inconclusive (never clean), the
report never carries a value, and the seed refuses to run anywhere but the environment it names.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import httpx
import pytest

from abacus.kernel.classification import mask
from abacus_tools import scrub_audit as sa
from abacus_tools.scrub_audit import Sample

RUN = "sa-0a1b2c3d"


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _clean_samples() -> list[Sample]:
    return [
        Sample("cloudwatch_logs", "g/s@1", f'{{"event": "scrub_audit.seeded", "run": "{RUN}"}}'),
        Sample("sentry", "event:1", f"scrub-audit {RUN}: could not match payee •••-••-5671"),
        Sample(
            "metrics",
            "abacus/abacus.scrub_audit.seeded",
            f"reason=payee •••-••-5671 outcome={RUN}",
        ),
    ]


# --- the scan -----------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [sa.SSN, sa.EIN, sa.ITIN], ids=["ssn", "ein", "itin"])
def test_a_seeded_tin_is_found_as_written(value: str) -> None:
    found = sa.scan(Sample("sentry", "event:9", f"payee {value} failed"), sa.SEEDED_TINS, ())
    assert [f.kind for f in found] == ["seeded"]
    assert found[0].masked == mask(value, "tin")


@pytest.mark.parametrize("value", [sa.SSN, sa.EIN, sa.ITIN], ids=["ssn", "ein", "itin"])
def test_a_seeded_tin_is_found_as_bare_digits_or_respaced(value: str) -> None:
    for text in (
        _digits(value),
        " ".join(_digits(value)),
        _digits(value)[:3] + "." + _digits(value)[3:],
    ):
        found = sa.scan(Sample("cloudwatch_logs", "g/s@2", f"tin={text}"), sa.SEEDED_TINS, ())
        assert any(f.kind == "seeded" for f in found), text


def test_a_masked_tin_is_not_a_finding() -> None:
    masked = mask(sa.SSN, "tin")
    assert (
        sa.scan(Sample("sentry", "event:3", f"payee {masked}"), sa.SEEDED_TINS, sa.SEEDED_OTHER)
        == []
    )


def test_a_valid_tin_the_seed_did_not_plant_is_found_too() -> None:
    unplanted = "900-71-2468"  # another 9xx ITIN form: valid, not seeded
    found = sa.scan(Sample("cloudwatch_logs", "g/s@4", f"ok {unplanted}"), sa.SEEDED_TINS, ())
    assert [f.kind for f in found] == ["tin"]
    assert found[0].masked.endswith("2468") and "900" not in found[0].masked


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        (sa.BANK_ACCOUNT, "bank_account"),
        (sa.DATE_OF_BIRTH, "date_of_birth"),
        (sa.IP_PIN, "ip_pin"),
    ],
)
def test_the_other_seeded_kinds_are_found_as_written(value: str, kind: str) -> None:
    found = sa.scan(Sample("sentry", "event:5", f"extra {value}"), (), sa.SEEDED_OTHER)
    assert [f.kind for f in found] == ["seeded"]
    assert value not in found[0].masked


@pytest.mark.source_scan
def test_the_seeded_forms_are_the_offline_suites() -> None:
    """The audit plants exactly what test_classification_scrubbing.py proves offline: the same
    expressions for the SSN, EIN and ITIN (the public repository holds no other TIN literal)."""
    root = Path(__file__).resolve().parents[3]
    offline = (root / "tests/security/test_classification_scrubbing.py").read_text(
        encoding="utf-8"
    )
    tool = (root / "src/abacus_tools/scrub_audit.py").read_text(encoding="utf-8")
    for name in ("ITIN", "SSN", "EIN"):
        expressions = [
            line.split("=", 1)[1].split("#")[0].strip()
            for text in (offline, tool)
            for line in text.splitlines()
            if line.startswith(f"{name}") and "=" in line
        ]
        assert len(expressions) == 2 and expressions[0] == expressions[1], name


# --- the verdict --------------------------------------------------------------------------------


def test_every_sink_delivered_and_nothing_found_is_clean() -> None:
    report = sa.audit("staging", RUN, _clean_samples())
    assert report.verdict == "clean" and report.exit_code() == 0
    assert report.sampled == {"cloudwatch_logs": 1, "sentry": 1, "metrics": 1}


def test_a_sink_that_never_received_the_marker_is_inconclusive_not_clean() -> None:
    samples = [s for s in _clean_samples() if s.sink != "sentry"]
    report = sa.audit("staging", RUN, samples)
    assert report.delivered["sentry"] is False
    assert report.verdict == "inconclusive" and report.exit_code() == 2


def test_any_finding_is_a_leak_and_the_report_carries_no_value() -> None:
    samples = [*_clean_samples(), Sample("cloudwatch_logs", "g/s@7", f"payee {sa.SSN}")]
    report = sa.audit("staging", RUN, samples)
    assert report.verdict == "leak" and report.exit_code() == 1
    body = json.dumps(report.as_json())
    for value in (*sa.SEEDED_TINS, *sa.SEEDED_OTHER):
        assert value not in body and _digits(value) not in _digits(body)


# --- the sink readers ---------------------------------------------------------------------------


class FakeLogs:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def describe_log_groups(self, **kwargs: object) -> Mapping[str, object]:
        if "nextToken" not in kwargs:
            return {
                "logGroups": [
                    {"logGroupName": "/abacus/staging/api"},
                    {"logGroupName": "/abacus/staging/vpc-flow"},
                ],
                "nextToken": "p2",
            }
        return {"logGroups": [{"logGroupName": "/abacus/staging/worker"}]}

    def filter_log_events(self, **kwargs: object) -> Mapping[str, object]:
        self.calls.append(kwargs)
        if "nextToken" not in kwargs:
            return {
                "events": [{"logStreamName": "s1", "timestamp": 1, "message": "one"}],
                "nextToken": "n2",
            }
        return {"events": [{"logStreamName": "s1", "timestamp": 2, "message": "two"}]}


def test_log_groups_page_and_skip_the_flow_log() -> None:
    groups = sa.log_groups(FakeLogs(), "staging", ["/aws/otel/abacus"])
    assert groups == ["/abacus/staging/api", "/abacus/staging/worker", "/aws/otel/abacus"]


def test_log_samples_page_within_the_window_and_name_their_location() -> None:
    logs = FakeLogs()
    samples = list(sa.log_samples(logs, ["/abacus/staging/api"], 100, 200))
    assert [s.text for s in samples] == ["one", "two"]
    assert samples[0].location == "/abacus/staging/api/s1@1"
    assert all(c["startTime"] == 100 and c["endTime"] == 200 for c in logs.calls)


def test_metric_samples_are_the_dimension_values() -> None:
    class FakeMetrics:
        def list_metrics(self, **kwargs: object) -> Mapping[str, object]:
            return {
                "Metrics": [
                    {
                        "MetricName": "abacus.scrub_audit.seeded",
                        "Dimensions": [
                            {"Name": "outcome", "Value": RUN},
                            {"Name": "reason", "Value": "x"},
                        ],
                    }
                ]
            }

    (sample,) = sa.metric_samples(FakeMetrics(), "abacus")
    assert sample.sink == "metrics" and RUN in sample.text and "reason=x" in sample.text


def test_sentry_samples_follow_the_link_header_and_stop_without_results() -> None:
    pages = {
        f"{sa._SENTRY_API}/projects/o/p/events/": (  # pyright: ignore[reportPrivateUsage] -- the base URL under test
            [{"eventID": "e1", "message": "m1"}],
            '<https://sentry.io/api/0/projects/o/p/events/?cursor=2>; rel="next"; results="true"',
        ),
        "https://sentry.io/api/0/projects/o/p/events/?cursor=2": (
            [{"eventID": "e2", "message": "m2"}],
            '<https://sentry.io/x?cursor=3>; rel="next"; results="false"',
        ),
    }

    def get(url: str, _params: Mapping[str, str]) -> httpx.Response:
        body, link = pages[url]
        return httpx.Response(
            200, json=body, headers={"link": link}, request=httpx.Request("GET", url)
        )

    samples = list(sa.sentry_samples(get, "o", "p", 60))
    assert [s.location for s in samples] == ["event:e1", "event:e2"]


# --- the guards and the offline check ------------------------------------------------------------


def test_the_seed_refuses_an_environment_it_does_not_run_in() -> None:
    with pytest.raises(sa.SeedError):
        sa.seed("staging")  # the test process is `test`, not staging


def test_sample_refuses_a_run_that_is_not_a_marker(capsys: pytest.CaptureFixture[str]) -> None:
    code = sa.main(["sample", "--env", "staging", "--run", "anything"])
    assert code == 2
    assert "refused" in capsys.readouterr().err


def test_check_scans_saved_samples_and_writes_the_report(tmp_path: Path) -> None:
    saved = tmp_path / "samples.jsonl"
    rows = [*_clean_samples(), Sample("metrics", "abacus/x", f"reason=ein {sa.EIN}")]
    saved.write_text("".join(json.dumps(s.__dict__) + "\n" for s in rows), encoding="utf-8")
    out = tmp_path / "report.json"
    code = sa.main(["check", "--input", str(saved), "--run", RUN, "--out", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert code == 1 and report["verdict"] == "leak"
    assert report["findings"] == [
        {
            "sink": "metrics",
            "location": "abacus/x",
            "kind": "seeded",
            "masked": mask(sa.EIN, "tin"),
        }
    ]


def test_a_next_page_off_sentrys_api_is_not_followed() -> None:
    """The bearer token rides on every page request: only Sentry's own API is followed."""
    nxt = sa._next_page  # pyright: ignore[reportPrivateUsage] -- the guard under test
    base = sa._SENTRY_API  # pyright: ignore[reportPrivateUsage] -- the base URL under test
    assert nxt('<https://evil.example.test/x?cursor=2>; rel="next"; results="true"') is None
    page = f"{base}/projects/o/p/events/?cursor=2"
    assert nxt(f'<{page}>; rel="next"; results="true"') == page
