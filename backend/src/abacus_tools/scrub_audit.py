"""The pre-shadow scrubbing audit (Q-03-T083; ADR-031, ADR-167; chapter 06 security suite). Runs as
an ops one-off task on the release image (`ops-task.yml`), in the environment it audits; never
from a laptop. Two steps, one run marker:

    python -m abacus_tools.scrub_audit seed --env staging
    python -m abacus_tools.scrub_audit sample --env staging --run sa-1a2b3c4d \
        --since-minutes 60 [--sentry-org <slug> --sentry-project <slug>] \
        [--metrics-namespace <ns>] [--log-group <name> ...] --out report.json

`seed` pushes the classification scrubber's seeded cases (the forms
`tests/security/test_classification_scrubbing.py` proves offline: an unmasked SSN, EIN and ITIN
from a tagged model, and a tagged model holding a bank account, a date of birth and an IP PIN)
through the real paths that leave the process: the kernel logger (CloudWatch through the task's
log driver), `error_tracking.report` (Sentry, `before_send=scrub`) and the scrubbing meter (the
OTLP metric export). Every seeded line carries the run marker, so `sample` can prove each sink
received the seed: a sink that never shows the marker makes the run inconclusive, not clean.

`sample` reads back what the sinks hold for the window: CloudWatch Logs events from every group
under `/abacus/<env>/` (plus `--log-group`), Sentry events for the project, and the dimension
values of the metrics in `--metrics-namespace`. Each text is checked for the seeded raw values (as
written or as bare nine digits) and for any valid SSN, ITIN or EIN form (`kernel.tin_patterns`),
so a real leak that the seed did not plant is found too.

The report is JSON of sinks, locations (log group and stream with the event time, Sentry event
id, metric name), the kind found and its mask, never a value. Exit 0 when every sink received the
marker and nothing was found, 1 when anything was found, 2 when a sink is inconclusive or the
command refused to run. Every finding becomes a test in `test_classification_scrubbing.py` before
the run is repeated (the acceptance; RB-42 says how).

`check --input samples.jsonl` runs the same scan offline on saved samples (one JSON object per
line: `sink`, `location`, `text`), e.g. an export a reviewer pulled by hand.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Annotated, Final, Literal, Protocol, cast

import httpx
from pydantic import BaseModel

from abacus.kernel.classification import PiiKind, classified, mask
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.tin_patterns import find_tins

Sink = Literal["cloudwatch_logs", "sentry", "metrics"]
SINKS: Final[tuple[Sink, ...]] = ("cloudwatch_logs", "sentry", "metrics")
AUDITED_ENVIRONMENTS: Final = ("staging", "production")
_MARKER: Final = re.compile(r"sa-[0-9a-f]{8}")
_SENTRY_API: Final = "https://sentry.io/api/0"
# The token is read from the task's environment (an ops secret), never an argument or a log line.
SENTRY_AUDIT_VAR: Final = "ABACUS_SENTRY_AUDIT_TOKEN"
# Upper bounds per sink, so one audit reads a sample, not the whole retention.
MAX_LOG_EVENTS_PER_GROUP: Final = 10_000
MAX_SENTRY_EVENTS: Final = 2_000

# --- the seeded cases ---------------------------------------------------------------------------
# The repository is public: the only TIN literal is a 9xx ITIN form; the SSN and EIN are assembled
# at run time, as the offline suite does. The other kinds never match a TIN pattern, so they are
# searched for as written.
ITIN: Final = "900-70-1234"  # 9xx area, middle pair 70: a valid ITIN, never an SSN (ADR-085)
SSN: Final = "-".join(("5" + "12", "3" + "4", "56" + "71"))  # area 512, group 34: valid
EIN: Final = "-".join(("4" + "1", "23" + "45678"))  # prefix 41 is assigned: valid
BANK_ACCOUNT: Final = "".join(("0" + "0", "0718", "2733", "91"))  # 12 digits, fake routing-free
DATE_OF_BIRTH: Final = "1961-04-" + "17"
IP_PIN: Final = "40" + "4172"
SEEDED_TINS: Final = (SSN, EIN, ITIN)
SEEDED_OTHER: Final = (BANK_ACCOUNT, DATE_OF_BIRTH, IP_PIN)
OTHER_KINDS: Final[tuple[PiiKind, ...]] = ("bank_account", "date_of_birth", "ip_pin")


class SeededPayee(BaseModel):
    """The tagged model the seed takes its values from (the kinds ADR-167 names)."""

    name: Annotated[str, classified("confidential")]
    tin: Annotated[str, classified("restricted", pii_kind="tin")]
    bank_account: Annotated[str, classified("restricted", pii_kind="bank_account")]
    date_of_birth: Annotated[str, classified("restricted", pii_kind="date_of_birth")]
    ip_pin: Annotated[str, classified("restricted", pii_kind="ip_pin")]


def new_marker() -> str:
    return f"sa-{uuid.uuid4().hex[:8]}"


class SeedError(RuntimeError):
    """The seed would not run here."""


def _guard(env: str) -> None:
    if env not in AUDITED_ENVIRONMENTS:
        raise SeedError(f"the audit runs only in {', '.join(AUDITED_ENVIRONMENTS)}")
    actual = settings().environment
    if actual != env:
        raise SeedError(
            f"this task runs in {actual!r}, not {env!r}: run it as that env's ops task"
        )


class SeededError(RuntimeError):
    """The seeded exception reported to Sentry; its message carries the seeded values."""


def seed(env: str, marker: str | None = None) -> str:
    """Push the seeded cases through the logger, Sentry and the meter; return the run marker."""
    _guard(env)
    run = marker or new_marker()
    # Imported here: they configure process-wide exporters, which only the seeding task needs.
    from abacus.kernel.error_tracking import configure_error_tracking, report
    from abacus.kernel.logging import get_logger
    from abacus.kernel.metrics import configure_metrics, meter, shutdown_metrics

    payee = SeededPayee(
        name="Scrub audit payee",
        tin=SSN,
        bank_account=BANK_ACCOUNT,
        date_of_birth=DATE_OF_BIRTH,
        ip_pin=IP_PIN,
    )
    log = get_logger("abacus_tools.scrub_audit")
    log.info(
        "scrub_audit.seeded",
        run=run,
        note=f"payee tin {payee.tin} checked",
        other=f"ein {EIN} itin {ITIN}",
    )
    log.warning(f"scrub_audit {run}: payee {payee.tin} failed")  # the event string itself
    with contextlib.suppress(TypeError, ValueError):  # refused is as good as dropped
        log.info("scrub_audit.model", run=run, payee=cast("object", payee))

    if configure_error_tracking("abacus-scrub-audit"):
        try:
            raise SeededError(f"scrub-audit {run}: could not match payee {payee.tin} (EIN {EIN})")
        except SeededError as exc:
            report(exc, error_type="SeededError", route=f"/scrub-audit/{payee.tin}")
        import sentry_sdk

        sentry_sdk.flush(timeout=10)
    else:
        log.warning("scrub_audit.sentry_off", run=run)

    configure_metrics("abacus-scrub-audit")
    counter = meter("abacus_tools.scrub_audit").create_counter("abacus.scrub_audit.seeded")
    counter.add(1, {"reason": f"payee {payee.tin}", "outcome": run})
    counter.add(1, {"reason": f"ein {EIN} itin {ITIN}", "outcome": run})
    shutdown_metrics()  # flushes the periodic exporter before the task exits
    return run


# --- the scan -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Sample:
    sink: Sink
    location: str  # never content: a log group/stream@time, a Sentry event id, a metric name
    text: str


@dataclass(frozen=True)
class Finding:
    sink: Sink
    location: str
    kind: Literal["seeded", "tin"]
    masked: str


@dataclass
class Report:
    env: str
    run: str
    sampled: dict[str, int] = field(default_factory=lambda: {s: 0 for s in SINKS})
    delivered: dict[str, bool] = field(default_factory=lambda: {s: False for s in SINKS})
    findings: list[Finding] = field(default_factory=lambda: list[Finding]())

    @property
    def verdict(self) -> Literal["clean", "leak", "inconclusive"]:
        if self.findings:
            return "leak"
        return "clean" if all(self.delivered.values()) else "inconclusive"

    def exit_code(self) -> int:
        return {"clean": 0, "leak": 1, "inconclusive": 2}[self.verdict]

    def as_json(self) -> dict[str, object]:
        return {
            "env": self.env,
            "run": self.run,
            "verdict": self.verdict,
            "sampled": self.sampled,
            "delivered": self.delivered,
            "findings": [asdict(f) for f in self.findings],
        }


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _nine_digit_runs(text: str) -> set[str]:
    return set(re.findall(r"\d{9}", re.sub(r"[\s\-./]", "", text)))


def scan(sample: Sample, seeded_tins: Sequence[str], seeded_other: Sequence[str]) -> list[Finding]:
    """Each seeded value present as written (or a seeded TIN as bare nine digits), and each valid
    TIN form present that is not a seeded one. Findings carry the mask, never the value."""
    found: list[Finding] = []
    runs = _nine_digit_runs(sample.text)
    for value in seeded_tins:
        if value in sample.text or _digits(value) in runs:
            found.append(Finding(sample.sink, sample.location, "seeded", mask(value, "tin")))
    for value, kind in zip(seeded_other, OTHER_KINDS, strict=False):
        if value in sample.text:
            found.append(Finding(sample.sink, sample.location, "seeded", mask(value, kind)))
    seeded_digits = {_digits(v) for v in seeded_tins}
    for match in find_tins(sample.text):
        if match.digits not in seeded_digits:
            found.append(Finding(sample.sink, sample.location, "tin", mask(match.digits, "tin")))
    return found


def audit(env: str, run: str, samples: Iterable[Sample]) -> Report:
    report = Report(env=env, run=run)
    for sample in samples:
        report.sampled[sample.sink] += 1
        if run in sample.text:
            report.delivered[sample.sink] = True
        report.findings.extend(scan(sample, SEEDED_TINS, SEEDED_OTHER))
    return report


# --- the sinks ----------------------------------------------------------------------------------


class LogsClient(Protocol):
    """The CloudWatch Logs calls the audit makes (boto3 `logs`; read only)."""

    def describe_log_groups(self, **kwargs: object) -> Mapping[str, object]: ...

    def filter_log_events(self, **kwargs: object) -> Mapping[str, object]: ...


class MetricsClient(Protocol):
    """The CloudWatch call the audit makes (boto3 `cloudwatch`; read only)."""

    def list_metrics(self, **kwargs: object) -> Mapping[str, object]: ...


def log_groups(client: LogsClient, env: str, extra: Sequence[str] = ()) -> list[str]:
    names: list[str] = []
    token: str | None = None
    while True:
        kwargs: dict[str, object] = {"logGroupNamePrefix": f"/abacus/{env}/"}
        if token:
            kwargs["nextToken"] = token
        page = client.describe_log_groups(**kwargs)
        groups = cast(list[Mapping[str, object]], page.get("logGroups", []))
        names.extend(str(g["logGroupName"]) for g in groups if "logGroupName" in g)
        token = cast(str | None, page.get("nextToken"))
        if not token:
            break
    # The VPC flow log holds packets, not application output.
    kept = [n for n in names if not n.endswith("/vpc-flow")]
    return sorted({*kept, *extra})


def log_samples(
    client: LogsClient, groups: Sequence[str], since_ms: int, until_ms: int
) -> Iterator[Sample]:
    for group in groups:
        token: str | None = None
        seen = 0
        while seen < MAX_LOG_EVENTS_PER_GROUP:
            kwargs: dict[str, object] = {
                "logGroupName": group,
                "startTime": since_ms,
                "endTime": until_ms,
                "limit": min(10_000, MAX_LOG_EVENTS_PER_GROUP - seen),
            }
            if token:
                kwargs["nextToken"] = token
            page = client.filter_log_events(**kwargs)
            events = cast(list[Mapping[str, object]], page.get("events", []))
            for event in events:
                seen += 1
                where = f"{group}/{event.get('logStreamName', '?')}@{event.get('timestamp', '?')}"
                yield Sample("cloudwatch_logs", where, str(event.get("message", "")))
            token = cast(str | None, page.get("nextToken"))
            if not token or not events:
                break


def metric_samples(client: MetricsClient, namespace: str) -> Iterator[Sample]:
    """Each metric's dimension values (OTLP attributes land as dimensions), as one text."""
    token: str | None = None
    while True:
        kwargs: dict[str, object] = {"Namespace": namespace, "RecentlyActive": "PT3H"}
        if token:
            kwargs["NextToken"] = token
        page = client.list_metrics(**kwargs)
        for metric in cast(list[Mapping[str, object]], page.get("Metrics", [])):
            dims = cast(list[Mapping[str, object]], metric.get("Dimensions", []))
            text = " ".join(f"{d.get('Name')}={d.get('Value')}" for d in dims)
            yield Sample("metrics", f"{namespace}/{metric.get('MetricName', '?')}", text)
        token = cast(str | None, page.get("NextToken"))
        if not token:
            break


def sentry_samples(
    get: Callable[[str, Mapping[str, str]], httpx.Response],
    org: str,
    project: str,
    since_minutes: int,
) -> Iterator[Sample]:
    """The project's events for the window, full bodies, newest first (Sentry's API pages by its
    Link header; `results="true"` marks a next page)."""
    url: str | None = f"{_SENTRY_API}/projects/{org}/{project}/events/"
    params = {"full": "true", "statsPeriod": f"{max(1, since_minutes)}m"}
    seen = 0
    while url and seen < MAX_SENTRY_EVENTS:
        response = get(url, params)
        response.raise_for_status()
        for event in cast(list[Mapping[str, object]], response.json()):
            seen += 1
            text = json.dumps(event, ensure_ascii=False, default=str)
            yield Sample("sentry", f"event:{event.get('eventID', event.get('id', '?'))}", text)
        url = _next_page(response.headers.get("link", ""))
        params = {}


def _next_page(link: str) -> str | None:
    for part in link.split(","):
        if 'rel="next"' in part and 'results="true"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


# --- the command line ---------------------------------------------------------------------------


def _logs_client() -> LogsClient:
    import boto3

    # No `logs` stubs in the lock (types-boto3 extras): the Protocol is the typed surface.
    return cast(LogsClient, boto3.client("logs"))  # pyright: ignore[reportUnknownMemberType] -- untyped service, region from the task's environment


def _metrics_client() -> MetricsClient:
    import boto3

    return cast(MetricsClient, boto3.client("cloudwatch"))  # pyright: ignore[reportUnknownMemberType] -- untyped service, region from the task's environment


def _sentry_get(token: str) -> Callable[[str, Mapping[str, str]], httpx.Response]:
    client = httpx.Client(timeout=30, headers={"Authorization": f"Bearer {token}"})

    def get(url: str, params: Mapping[str, str]) -> httpx.Response:
        return client.get(url, params=dict(params))

    return get


def sample_sinks(args: argparse.Namespace) -> Report:
    if args.env not in AUDITED_ENVIRONMENTS:
        raise SeedError(f"the audit runs only in {', '.join(AUDITED_ENVIRONMENTS)}")
    if not _MARKER.fullmatch(args.run):
        raise SeedError("--run must be the marker `seed` printed (sa-xxxxxxxx)")
    until_ms = int(system_now().timestamp() * 1000)
    since_ms = until_ms - args.since_minutes * 60_000
    logs = _logs_client()
    samples: list[Iterable[Sample]] = [
        log_samples(logs, log_groups(logs, args.env, args.log_group), since_ms, until_ms)
    ]
    if args.metrics_namespace:
        metrics = _metrics_client()
        samples.append(metric_samples(metrics, args.metrics_namespace))
    if args.sentry_org and args.sentry_project:
        token = os.environ.get(SENTRY_AUDIT_VAR)
        if not token:
            raise SeedError(f"{SENTRY_AUDIT_VAR} is not set: Sentry cannot be sampled")
        samples.append(
            sentry_samples(
                _sentry_get(token), args.sentry_org, args.sentry_project, args.since_minutes
            )
        )
    return audit(args.env, args.run, (s for group in samples for s in group))


def _read_samples(path: str) -> Iterator[Sample]:
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                raw = cast(dict[str, str], json.loads(line))
                yield Sample(cast(Sink, raw["sink"]), raw["location"], raw["text"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.scrub_audit", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seed_cmd = commands.add_parser("seed", help="push the seeded cases through every sink")
    seed_cmd.add_argument("--env", required=True, choices=AUDITED_ENVIRONMENTS)
    sample_cmd = commands.add_parser("sample", help="read the sinks back and scan them")
    sample_cmd.add_argument("--env", required=True, choices=AUDITED_ENVIRONMENTS)
    sample_cmd.add_argument("--run", required=True)
    sample_cmd.add_argument("--since-minutes", type=int, default=60)
    sample_cmd.add_argument("--log-group", action="append", default=[])
    sample_cmd.add_argument("--metrics-namespace")
    sample_cmd.add_argument("--sentry-org")
    sample_cmd.add_argument("--sentry-project")
    sample_cmd.add_argument("--out")
    check_cmd = commands.add_parser("check", help="scan saved samples offline")
    check_cmd.add_argument("--input", required=True)
    check_cmd.add_argument("--run", required=True)
    check_cmd.add_argument("--env", default="staging")
    check_cmd.add_argument("--out")
    args = parser.parse_args(argv)

    try:
        if args.command == "seed":
            print(json.dumps({"run": seed(args.env)}))
            return 0
        report = (
            sample_sinks(args)
            if args.command == "sample"
            else audit(args.env, args.run, _read_samples(args.input))
        )
    except SeedError as exc:
        print(json.dumps({"refused": str(exc)}), file=sys.stderr)
        return 2
    body = json.dumps(report.as_json(), indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(body + "\n")
    print(body)
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
