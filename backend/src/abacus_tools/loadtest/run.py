"""The load-test harness, part 1 (Q-03-T035; Q-03 E1; QD-6). `make loadtest PROFILE=<p>`.

Run: python -m abacus_tools.loadtest.run --profile smoke
         [--scenario PATH] [--base-url URL] [--temporal-target HOST:PORT] [--var NAME=VALUE]
         [--out DIR]

Plays a YAML scenario (`scenario.py`, `scenarios/*.yaml`) against a local stack with `httpx` and
`asyncio` only (no new dependency): virtual users loop over weighted endpoint groups, SSE streams
are read with `httpx` (time to first event), and Temporal-client operations run at a rate. Every
sample is timed on the client; the report gives p50/p95/p99, max, count, errors and rate per
group, and the pass rule's verdict (`stats.verdict`). It is written as JSON and Markdown under
`backend/.local/loadtest/` (git-ignored: results only, never client data) and printed.

Local only: the API and Temporal targets must be loopback addresses and the environment `local`
or `test`, and tokens are signed with the local sign-in server's key (`fakes.oidc_server`), which
only a local API trusts. It never reaches a hosted environment, a database or AWS directly.
Exit codes: 0 passed, 1 the pass rule failed, 2 refused or misconfigured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from string import Formatter

import httpx
from temporalio.client import Client

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus_tools.loadtest.scenario import Scenario, Stream, TemporalOp, load, profile
from abacus_tools.loadtest.stats import GroupResult, Samples, Verdict, summarise, verdict
from abacus_tools.stack import is_loopback

OUT = Path(__file__).resolve().parents[3] / ".local" / "loadtest"
DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_TEMPORAL = "127.0.0.1:7233"
LOCAL_NAMESPACE = "default"
_LOCAL_ENVIRONMENTS = frozenset({"local", "test"})
TemporalCall = Callable[[TemporalOp], Awaitable[object]]


class Refused(Exception):
    """The harness will not run against this target."""


def check_local(
    base_url: str, temporal_target: str | None, *, starts_in: str | None = None
) -> None:
    """Loopback targets in a local or test environment only (QD-6: never a hosted build).
    `starts_in`: the namespace a scenario would start workflows in, which must be the local
    default one (security review, DEC-397)."""
    if starts_in is not None and starts_in != LOCAL_NAMESPACE:
        raise Refused(f"start_workflow runs only in the local {LOCAL_NAMESPACE!r} namespace")
    if settings().environment not in _LOCAL_ENVIRONMENTS:
        raise Refused(f"environment {settings().environment!r} is not local")
    if not base_url.startswith(("http://", "https://")) or not is_loopback(base_url):
        raise Refused(f"{base_url} is not a loopback address")
    if temporal_target is not None and not is_loopback(temporal_target):
        raise Refused(f"{temporal_target} is not a loopback address")


def _fill(path: str, variables: Mapping[str, str]) -> str:
    missing = [f for _, f, _, _ in Formatter().parse(path) if f and f not in variables]
    if missing:
        raise ValueError(f"{path} needs --var {missing[0]}=...")
    return path.format_map(dict(variables))


def _paths(scenario: Scenario, variables: Mapping[str, str]) -> None:
    """Every placeholder has a value before anything runs."""
    for group in scenario.groups:
        for step in group.steps:
            _fill(step.path, variables)
    for stream in scenario.streams:
        _fill(stream.path, variables)


@dataclass(frozen=True)
class Report:
    scenario: str
    started_at: str
    seconds: float
    users: int
    groups: list[GroupResult]
    verdict: Verdict


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


async def run(
    scenario: Scenario,
    client: httpx.AsyncClient,
    *,
    token: str | None = None,
    temporal: TemporalCall | None = None,
    variables: Mapping[str, str] | None = None,
) -> Report:
    """Play `scenario` with `client` (its base URL set) and report per group."""
    given = dict(variables or {})
    _paths(scenario, given)
    if scenario.temporal and temporal is None:
        raise ValueError("the scenario has Temporal operations but no Temporal client")
    auth = {"Authorization": f"Bearer {token}"} if token else {}
    samples: dict[str, Samples] = {g.name: Samples("http", g.p95_ms) for g in scenario.groups}
    for s in scenario.streams:
        samples[s.name] = Samples("sse", s.p95_first_event_ms)
    for t in scenario.temporal:
        samples[t.name] = Samples("temporal", t.p95_ms)
    started_at = system_now()
    began = time.perf_counter()
    deadline = began + scenario.duration_seconds
    groups = scenario.groups
    weights = [g.weight for g in groups]

    async def user(n: int) -> None:
        rng = random.Random(scenario.seed + n)
        while groups and time.perf_counter() < deadline:
            group = rng.choices(groups, weights)[0]
            for step in group.steps:
                headers = auth if step.auth else {}
                start = time.perf_counter()
                try:
                    response = await client.request(
                        step.method,
                        _fill(step.path, given),
                        json=step.json_body,
                        headers=headers,
                    )
                except httpx.HTTPError as exc:
                    samples[group.name].failed(type(exc).__name__, _ms(start))
                    continue
                if response.status_code in step.expect:
                    samples[group.name].ok(_ms(start))
                else:
                    samples[group.name].failed(str(response.status_code), _ms(start))
            if scenario.think_ms:
                await asyncio.sleep(scenario.think_ms / 1000)

    async def stream(spec: Stream) -> None:
        found = samples[spec.name]
        start = time.perf_counter()
        headers = {**auth, "Accept": "text/event-stream"}
        first: float | None = None
        try:
            async with client.stream("GET", _fill(spec.path, given), headers=headers) as resp:
                if resp.status_code != 200:
                    found.failed(str(resp.status_code), _ms(start))
                    return
                try:
                    async with asyncio.timeout(spec.hold_seconds):
                        async for line in resp.aiter_lines():
                            if first is None and line.startswith(("data:", "event:", "id:")):
                                first = _ms(start)
                                found.ok(first)
                except TimeoutError:
                    pass  # held for the scenario's time: the stream is closed on purpose
        except httpx.HTTPError as exc:
            found.failed(type(exc).__name__, _ms(start))
            return
        if first is None:
            found.failed("no_event")

    async def operate(op: TemporalOp, call: TemporalCall) -> None:
        found = samples[op.name]
        interval = 1 / op.rate_per_second
        due = time.perf_counter()
        while time.perf_counter() < deadline:
            start = time.perf_counter()
            try:
                await call(op)
                found.ok(_ms(start))
            except Exception as exc:  # any client error is a sample, by class name only
                found.failed(type(exc).__name__, _ms(start))
            due += interval
            await asyncio.sleep(max(0.0, due - time.perf_counter()))

    tasks: list[Awaitable[None]] = [user(n) for n in range(scenario.users)]
    tasks += [stream(s) for s in scenario.streams for _ in range(s.count)]
    if temporal is not None:
        tasks += [operate(op, temporal) for op in scenario.temporal]
    await asyncio.gather(*tasks)
    seconds = time.perf_counter() - began
    results = [summarise(name, found, seconds) for name, found in samples.items()]
    return Report(
        scenario.name,
        started_at.isoformat(),
        round(seconds, 3),
        scenario.users,
        results,
        verdict(results, scenario.max_error_rate),
    )


def temporal_caller(client: Client) -> TemporalCall:
    async def call(op: TemporalOp) -> object:
        if op.kind == "count_workflows":
            return await client.count_workflows(op.query)
        return await client.start_workflow(
            op.workflow or "",
            args=list(op.args),
            id=f"loadtest-{op.name}-{uuid.uuid4()}",
            task_queue=op.task_queue or "",
        )

    return call


def markdown(report: Report) -> str:
    lines = [
        f"# Load test: {report.scenario}",
        "",
        f"Started {report.started_at}, {report.seconds} s, {report.users} users. "
        f"Verdict: **{'passed' if report.verdict.passed else 'failed'}** "
        f"(error rate {report.verdict.error_rate:.4%}).",
        "",
        "| Group | Kind | Count | Errors | p50 ms | p95 ms | p99 ms | Max ms | Per s | p95 target "
        "|",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in report.groups:
        cells = [g.name, g.kind, g.count, g.errors, g.p50_ms, g.p95_ms, g.p99_ms, g.max_ms]
        cells += [g.per_second, g.target_p95_ms]
        lines.append("| " + " | ".join("—" if c is None else str(c) for c in cells) + " |")
    lines += [f"- {r}" for r in report.verdict.reasons]
    return "\n".join(lines) + "\n"


def write_report(report: Report, out: Path) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    stamp = report.started_at[:19].replace("-", "").replace(":", "")
    base = out / f"{report.scenario}-{stamp}Z"
    as_json = base.with_suffix(".json")
    as_md = base.with_suffix(".md")
    as_json.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
    as_md.write_text(markdown(report))
    return as_json, as_md


def _token(persona: str | None, seconds: float) -> str | None:
    if persona is None:
        return None
    from abacus_tools.fakes.oidc_server import provider  # local sign-in key; local only

    return provider().token(persona, mfa=True, expires_in=int(seconds) + 300)


async def _main(args: argparse.Namespace, scenario: Scenario) -> Report:
    temporal: TemporalCall | None = None
    if scenario.temporal:
        connected = await Client.connect(args.temporal_target, namespace=args.namespace)
        temporal = temporal_caller(connected)
    limits = httpx.Limits(max_connections=scenario.users + sum(s.count for s in scenario.streams))
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0, limits=limits) as client:
        return await run(
            scenario,
            client,
            token=_token(scenario.persona, scenario.duration_seconds),
            temporal=temporal,
            variables=dict(v.split("=", 1) for v in args.var),
        )


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.loadtest.run", description=__doc__)
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--scenario", type=Path, default=None)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--temporal-target", default=settings().temporal_target or DEFAULT_TEMPORAL
    )
    parser.add_argument("--namespace", default=settings().temporal_namespace)
    parser.add_argument("--var", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(list(argv))
    try:
        scenario = load(args.scenario) if args.scenario else profile(args.profile)
        starts = any(op.kind == "start_workflow" for op in scenario.temporal)
        check_local(
            args.base_url,
            args.temporal_target if scenario.temporal else None,
            starts_in=args.namespace if starts else None,
        )
        if any("=" not in v for v in args.var):
            raise ValueError("--var takes NAME=VALUE")
        report = asyncio.run(_main(args, scenario))
    except (Refused, ValueError) as exc:
        print(f"loadtest refused: {exc}", file=sys.stderr)
        return 2
    as_json, _ = write_report(report, args.out)
    print(markdown(report))
    print(f"written {as_json} (and .md)")
    return 0 if report.verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
