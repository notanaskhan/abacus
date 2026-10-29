"""The weekly quality report (Q-03-T003; chapter 10 §10.14).

Run: python -m abacus_tools.quality.report --inputs DIR [--since DATE] [--until DATE]
                                            [--out FILE] [--json FILE]

One table per metric area of chapter 10 §10.14.2: CI, Flow, Tests, Security, Contracts, Journeys,
Design, Accessibility, Compute, AI, Ops and Cost. Every area always prints; a metric whose source
is missing reads "no data" with the source it waits for, so a gap is visible rather than silent.

It reads files only. It opens no network connection, writes nothing inside the repository, and
neither builds nor deploys anything: `.github/workflows/quality-report.yml` gathers the inputs
with `gh` into a temporary directory and publishes the result as the job summary and an artifact
(working agreement: a report must not cost a commit, a build or a deploy).

Inputs in DIR, each optional:
  runs.json        gh run list --branch main --json workflowName,status,conclusion,createdAt,
                   updatedAt,event
  prs.json         gh pr list --state merged --json number,additions,deletions,createdAt,
                   mergedAt,reviews
  coverage.json    `coverage json` over the combined CI data
  mutation.json    {"modules": {"<module>": {"killed": n, "survived": n}}} (mutation wiring)
  parity.json      apps/web parity-report/parity.json (F-05-T16)
  journeys.json    the Playwright JSON reporter's output
  evals/*.json     eval run summaries (`abacus_tools.evals`)
  loadtest-trend.json  the x1 load smoke's p95 trend (`abacus_tools.loadtest.trend --out`)
And from the repository: docs/quality/backfill.md, docs/quality/escaped-defects.md, the
capacity ledger's refused-requests table, and the `# ac-test-author:` headers and strict xfails in
the test trees.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

from abacus.kernel.clock import system_now

REPO = Path(__file__).resolve().parents[4]
AREAS = (
    "CI",
    "Flow",
    "Tests",
    "Security",
    "Contracts",
    "Journeys",
    "Design",
    "Accessibility",
    "Compute",
    "AI",
    "Ops",
    "Cost",
)
Status = Literal["ok", "breach", "reported", "no data"]
Json = Mapping[str, object]

PR_SIZE_TARGET = 600
MAIN_GREEN_TARGET = 95.0
COVERAGE_FLOOR = 95.0
RED_LINE_FLOOR = 97.0
EVAL_SPEND_MONTHLY = 200.0
_STRICT_XFAIL = re.compile(r"xfail\([^)]*strict\s*=\s*True", re.DOTALL)
_AUTHOR_HEADER = re.compile(r"^(#|//) ac-test-author: \S+", re.MULTILINE)


@dataclass(frozen=True)
class Row:
    area: str
    metric: str
    value: str
    target: str
    status: Status
    source: str


@dataclass(frozen=True)
class Window:
    since: date
    until: date

    def holds(self, when: date) -> bool:
        return self.since <= when <= self.until


class ReportError(ValueError):
    pass


# --- reading -------------------------------------------------------------------------------------


def _load_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    try:
        return cast(object, json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise ReportError(f"{path.name} is not valid JSON: {exc}") from exc


def _records(value: object) -> list[Json]:
    if not isinstance(value, list):
        return []
    return [cast(Json, item) for item in cast(list[object], value) if isinstance(item, dict)]


def _when(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _num(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _money(value: object) -> float:
    """A cost as the eval summaries serialise it: a Decimal written as a string, or a number."""
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return _num(value)


def table_rows(markdown: str, first_header: str) -> list[dict[str, str]]:
    """The body rows of every markdown table whose first header cell is `first_header`."""
    out: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in markdown.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None:
            header = cells if cells[0] == first_header else []
        elif header and not set(line) <= set("|-: "):
            out.append(dict(zip(header, cells, strict=False)))
    return out


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    return statistics.quantiles(ordered, n=100, method="inclusive")[round(q * 100) - 1]


# --- areas ---------------------------------------------------------------------------------------


def ci_rows(runs: object, window: Window) -> Iterator[Row]:
    src = "runs.json (gh run list --branch main)"
    done = [
        r
        for r in _records(runs)
        if r.get("status") == "completed"
        and (created := _when(r.get("createdAt"))) is not None
        and window.holds(created.date())
    ]
    ci = sorted(
        (r for r in done if r.get("workflowName") == "ci"),
        key=lambda r: cast(datetime, _when(r.get("createdAt"))),
    )
    verdicts = [r for r in ci if r.get("conclusion") in ("success", "failure")]
    if verdicts:
        end = datetime.combine(window.until + timedelta(days=1), datetime.min.time()).replace(
            tzinfo=cast(datetime, _when(verdicts[0].get("createdAt"))).tzinfo
        )
        green = total = 0.0
        for run, nxt in zip(verdicts, [*verdicts[1:], None], strict=True):
            start = cast(datetime, _when(run.get("createdAt")))
            stop = cast(datetime, _when(nxt.get("createdAt"))) if nxt is not None else end
            span = max((stop - start).total_seconds(), 0.0)
            total += span
            green += span if run.get("conclusion") == "success" else 0.0
        share = 100.0 * green / total if total else 100.0
        yield Row(
            "CI",
            "Share of time main is green",
            f"{share:.1f}% over {len(verdicts)} finished runs",
            f">= {MAIN_GREEN_TARGET:.0f}%",
            "ok" if share >= MAIN_GREEN_TARGET else "breach",
            src,
        )
    else:
        yield Row("CI", "Share of time main is green", "no data", ">= 95%", "no data", src)
    durations: dict[str, list[float]] = {}
    for run in done:
        start, stop = _when(run.get("createdAt")), _when(run.get("updatedAt"))
        if start is not None and stop is not None and run.get("conclusion") == "success":
            name = str(run.get("workflowName", "?"))
            durations.setdefault(name, []).append((stop - start).total_seconds() / 60)
    if durations:
        parts = [
            f"{name} p50 {_percentile(v, 0.5):.0f} / p90 {_percentile(v, 0.9):.0f} min"
            for name, v in sorted(durations.items())
        ]
        yield Row("CI", "Workflow durations", "; ".join(parts), "§10.4.2 budgets", "reported", src)
    else:
        yield Row("CI", "Workflow durations", "no data", "§10.4.2 budgets", "no data", src)
    yield Row(
        "CI",
        "Flaky tests in quarantine; oldest age",
        "no data",
        "<= 5; <= 10 working days",
        "no data",
        "quarantine marker (F-01)",
    )


def flow_rows(
    prs: object, escaped: str | None, ledger: str | None, window: Window
) -> Iterator[Row]:
    src = "prs.json (gh pr list --state merged)"
    merged = [
        p
        for p in _records(prs)
        if (when := _when(p.get("mergedAt"))) is not None and window.holds(when.date())
    ]
    if merged:
        sizes = [_num(p.get("additions")) + _num(p.get("deletions")) for p in merged]
        median = statistics.median(sizes)
        yield Row(
            "Flow",
            "PR size, median lines changed",
            f"{median:.0f} over {len(merged)} merged PRs",
            f"<= {PR_SIZE_TARGET}",
            "ok" if median <= PR_SIZE_TARGET else "breach",
            src,
        )
        hours = [
            (cast(datetime, _when(p.get("mergedAt"))) - created).total_seconds() / 3600
            for p in merged
            if (created := _when(p.get("createdAt"))) is not None
        ]
        reviewed = [p for p in merged if _records(p.get("reviews"))]
        latency = f"open to merge median {statistics.median(hours):.1f} h" if hours else "no data"
        latency += f"; {len(reviewed)} of {len(merged)} PRs reviewed"
        yield Row(
            "Flow",
            "Review latency",
            latency,
            "red <= 1 working day, amber <= 2",
            "reported",
            src + " (solo edition: optional self-review)",
        )
    else:
        yield Row("Flow", "PR size, median lines changed", "no data", "<= 600", "no data", src)
        yield Row("Flow", "Review latency", "no data", "red <= 1 day", "no data", src)
    yield from _escaped_rows(escaped, window)
    yield Row(
        "Flow",
        "Change failure rate; SEV1 time to restore",
        "no data",
        "<= 10%; <= 4 h",
        "no data",
        "production releases (from M9)",
    )
    refused = table_rows(ledger, "Date") if ledger is not None else []
    in_window = [r for r in refused if _date_in(r.get("Date", ""), window)]
    yield Row(
        "Flow",
        "Reserve requests refused or moved (Q-03)",
        f"{len(in_window)} this window, {len(refused)} in all",
        "never spent on a feature",
        "reported",
        "docs/product/capacity-ledger.md",
    )


def _date_in(text: str, window: Window) -> bool:
    try:
        return window.holds(date.fromisoformat(text[:10]))
    except ValueError:
        return False


def _escaped_rows(escaped: str | None, window: Window) -> Iterator[Row]:
    src = "docs/quality/escaped-defects.md"
    if escaped is None:
        yield Row("Flow", "Escaped defects", "no data", "0 in green", "no data", src)
        return
    rows = [r for r in table_rows(escaped, "ID") if _date_in(r.get("Found", ""), window)]
    zones = Counter(r.get("Zone", "?") for r in rows)
    layers = Counter(r.get("Should have been caught by", "?") for r in rows)
    still_open = sum(1 for r in rows if r.get("State") == "open")
    by_zone = ", ".join(f"{z} {n}" for z, n in sorted(zones.items())) or "none"
    by_layer = ", ".join(f"{k} {n}" for k, n in sorted(layers.items())) or "none"
    yield Row(
        "Flow",
        "Escaped defects, by zone and by the layer that should have caught them",
        f"{len(rows)} ({by_zone}); layers: {by_layer}; {still_open} open",
        "0 in green for 4 sprints",
        "breach" if zones.get("green", 0) else "ok",
        src,
    )


def backfill_rows(tracker: str | None) -> Iterator[Row]:
    src = "docs/quality/backfill.md"
    if tracker is None:
        yield Row(
            "Tests", "Back-fill burn-down", "no data", "55 -> 0 by Apr 30, 2027", "no data", src
        )
        return
    statuses = Counter(r.get("Status", "?") for r in table_rows(tracker, "TASK"))
    owed = statuses.get("scheduled", 0)
    parts = ", ".join(f"{name} {n}" for name, n in sorted(statuses.items()))
    yield Row(
        "Tests",
        "Back-fill burn-down",
        f"{owed} still owed of {sum(statuses.values())} ({parts})",
        "55 -> 0 by Apr 30, 2027",
        "ok" if owed == 0 else "reported",
        src,
    )


def coverage_rows(coverage: object) -> Iterator[Row]:
    src = "coverage.json (coverage combine; coverage json)"
    if not isinstance(coverage, dict):
        yield Row("Tests", "Coverage, global", "no data", ">= 95%", "no data", src)
        yield Row(
            "Tests", "Coverage, per module", "no data", ">= 97% on red from S13", "no data", src
        )
        return
    data = cast(Json, coverage)
    totals = cast(Json, data.get("totals", {}))
    pct = _num(totals.get("percent_covered"))
    yield Row(
        "Tests",
        "Coverage, global",
        f"{pct:.1f}%",
        f">= {COVERAGE_FLOOR:.0f}%",
        "ok" if pct >= COVERAGE_FLOOR else "breach",
        src,
    )
    modules: dict[str, list[float]] = {}
    for name, entry in cast(Json, data.get("files", {})).items():
        match = re.search(r"abacus/modules/([a-z_]+)/", name.replace("\\", "/"))
        if match and isinstance(entry, dict):
            summary = cast(Json, cast(Json, entry).get("summary", {}))
            pair = modules.setdefault(match.group(1), [0.0, 0.0])
            pair[0] += _num(summary.get("covered_lines"))
            pair[1] += _num(summary.get("num_statements"))
    low = sorted(
        (100.0 * covered / total, name)
        for name, (covered, total) in modules.items()
        if total and 100.0 * covered / total < RED_LINE_FLOOR
    )
    value = (
        ", ".join(f"{name} {p:.1f}%" for p, name in low) if low else f"all {len(modules)} >= 97%"
    )
    yield Row(
        "Tests",
        "Coverage, modules below 97% line",
        value if modules else "no data",
        ">= 97% line on red modules from S13",
        "reported" if modules else "no data",
        src,
    )


def mutation_rows(mutation: object) -> Iterator[Row]:
    src = "mutation.json (mutation wiring, Q-03 workstream C)"
    modules = cast(Json, mutation).get("modules") if isinstance(mutation, dict) else None
    if not isinstance(modules, dict) or not modules:
        yield Row("Tests", "Mutation score per module", "no data", ">= floor", "no data", src)
        return
    parts: list[str] = []
    for name, entry in sorted(cast(Json, modules).items()):
        counts: Json = cast(Json, entry) if isinstance(entry, dict) else {}
        killed, survived = _num(counts.get("killed")), _num(counts.get("survived"))
        total = killed + survived
        parts.append(f"{name} {100.0 * killed / total:.0f}%" if total else f"{name} n/a")
    yield Row("Tests", "Mutation score per module", ", ".join(parts), ">= floor", "reported", src)


def authorship_rows(repo: Path) -> Iterator[Row]:
    files = list(_test_files(repo))
    authored = sum(1 for _, text in files if _AUTHOR_HEADER.search(text))
    held = sum(len(_STRICT_XFAIL.findall(text)) for _, text in files)
    yield Row(
        "Tests",
        "Independent AC suites (files headed ac-test-author)",
        str(authored),
        "every amber and red task",
        "reported",
        "backend/tests, apps/web/src",
    )
    yield Row(
        "Tests",
        "Defects held by strict xfail tests",
        str(held),
        "each recorded in its task file",
        "reported",
        "backend/tests",
    )


def _test_files(repo: Path) -> Iterator[tuple[Path, str]]:
    for root, patterns in (
        (repo / "backend" / "tests", ("test_*.py",)),
        (repo / "apps" / "web" / "src", ("*.test.ts", "*.test.tsx")),
    ):
        for pattern in patterns:
            for path in root.rglob(pattern) if root.is_dir() else ():
                if "node_modules" not in path.parts:
                    yield path, path.read_text(encoding="utf-8", errors="replace")


def security_rows(repo: Path) -> Iterator[Row]:
    files = sorted((repo / "backend" / "tests" / "security").glob("test_*.py"))
    yield Row(
        "Security",
        "Security test files",
        f"{len(files)} files",
        "per §10.3.4",
        "reported",
        "backend/tests/security",
    )
    yield Row(
        "Security",
        "Open pen-test findings by severity and age",
        "no data",
        "0 critical or high at any gate",
        "no data",
        "pen test #1 (Q-03-T019, Feb 2027)",
    )


def contract_rows(repo: Path) -> Iterator[Row]:
    root = repo / "backend" / "tests" / "contracts"
    suites = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name != "__pycache__")
    yield Row(
        "Contracts",
        "Consumer contract suites",
        f"{len(suites)} suites",
        "all green in provider CI",
        "reported",
        "backend/tests/contracts",
    )
    drift = fixture_drift(repo)
    yield Row(
        "Contracts",
        "Fixture-versus-live drift; unverified fakes",
        "no data" if drift is None else f"{len(drift)} routes; not measured",
        "0; 0",
        "no data" if drift is None else "reported",
        "fixture handler keys against packages/api-client/openapi.json (Q-03-T061)",
    )


_FIXTURE_KEY = re.compile(r"[\"'`](GET|POST|PUT|PATCH|DELETE) (/v1/[a-z][A-Za-z0-9_{}./-]*)[\"'`]")


def fixture_drift(repo: Path) -> list[str] | None:
    """Q-03-T061: the routes fixture mode answers that the OpenAPI document has not (the same
    count `apps/web/src/fixtures/route-drift.test.ts` holds at its known list); None without the
    document ("no data", as every missing source reads)."""
    document = repo / "packages" / "api-client" / "openapi.json"
    if not document.is_file():
        return None
    spec = json.loads(document.read_text("utf-8"))

    def shape(path: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", path)

    live = {
        f"{method.upper()} {shape(path)}"
        for path, ops in cast(dict[str, dict[str, object]], spec["paths"]).items()
        for method in ops
        if method in ("get", "post", "put", "patch", "delete")
    }
    web = repo / "apps" / "web" / "src"
    answered: set[str] = set()
    for folder in (web / "fixtures", web / "app-core"):
        for path in folder.rglob("*.ts"):
            if path.name.endswith(".test.ts"):
                continue
            for method, route in _FIXTURE_KEY.findall(path.read_text("utf-8")):
                answered.add(f"{method} {shape(route)}")
    return sorted(answered - live)


def journey_rows(journeys: object) -> Iterator[Row]:
    src = "journeys.json (Playwright JSON reporter)"
    stats = cast(Json, journeys).get("stats") if isinstance(journeys, dict) else None
    if not isinstance(stats, dict):
        yield Row("Journeys", "Journey specs passing", "no data", "on plan", "no data", src)
    else:
        s = cast(Json, stats)
        passed, failed = int(_num(s.get("expected"))), int(_num(s.get("unexpected")))
        flaky = int(_num(s.get("flaky")))
        yield Row(
            "Journeys",
            "Journey specs passing",
            f"{passed} passed, {failed} failed, {flaky} flaky",
            "on plan, 0 failed",
            "ok" if failed == 0 else "breach",
            src,
        )
    yield Row("Journeys", "INV violations", "no data", "0", "no data", "invariant checker (F-04)")


def design_rows(parity: object) -> Iterator[Row]:
    src = "parity.json (F-05-T16)"
    rows = _records(cast(Json, parity).get("rows")) if isinstance(parity, dict) else []
    if not rows:
        yield Row(
            "Design", "Parity rows; Tier A/D failures", "no data", "0 A/D failures", "no data", src
        )
        return
    failed = [r for r in rows if r.get("status") not in ("passed", "skipped")]
    blocking = [r for r in failed if str(r.get("tier", "")).upper() in ("A", "D")]
    diffs = [_num(r.get("diffPercent")) for r in rows if r.get("diffPercent") is not None]
    median = f"; median diff {statistics.median(diffs):.2f}%" if diffs else ""
    yield Row(
        "Design",
        "Parity rows; Tier A/D failures",
        f"{len(rows)} rows, {len(failed)} failed, {len(blocking)} Tier A/D{median}",
        "0 Tier A/D failures",
        "breach" if blocking else "ok",
        src,
    )


def placeholder_rows() -> Iterator[Row]:
    yield Row(
        "Accessibility",
        "Serious or critical axe findings; open manual-audit items",
        "no data",
        "0; 0 at M10",
        "no data",
        "axe results in the journey and gallery runs",
    )
    yield Row(
        "Compute",
        "Engines live with a current signed CPA review",
        "no data",
        "100% of non-synthetic use",
        "no data",
        "compute engines (T- and K- epics)",
    )
    yield Row(
        "Ops",
        "SLO burn; canary; restore-drill age; last load test",
        "no data",
        "99.9%; >= 99%; <= 1 quarter; pass",
        "no data",
        "staging and production (Q-01)",
    )


def load_rows(found: object) -> Iterator[Row]:
    """The x1 load smoke's p95 against its 4-week median (Q-03-T043; chapter 10 §10.11.5)."""
    metric = "x1 load smoke: p95 per group against its 4-week median"
    target = "no group more than 20% over"
    src = "loadtest-trend.json"
    if not isinstance(found, dict):
        yield Row("Ops", metric, "no data", target, "no data", src)
        return
    trend = cast(Json, found)
    groups = cast(list[Json], trend.get("groups") or [])
    regressed = [str(g.get("name")) for g in groups if g.get("regressed")]
    compared = [g for g in groups if g.get("rise") is not None]
    value = (
        f"{len(compared)} of {len(groups)} groups compared, {len(regressed)} over "
        f"(run {trend.get('run_started_at')})"
    )
    if regressed:
        value += f": {', '.join(regressed)}"
    status: Status = "breach" if regressed else ("ok" if compared else "reported")
    yield Row("Ops", metric, value, target, status, src)


def ai_rows(summaries: Sequence[Json], window: Window) -> Iterator[Row]:
    src = "evals/*.json (eval summaries)"
    recent = [
        s for s in summaries if (w := _when(s.get("finished_at"))) and window.holds(w.date())
    ]
    if not recent:
        yield Row(
            "AI", "Eval suites passing", "no data", "100% of cleared capabilities", "no data", src
        )
        return
    latest: dict[str, Json] = {}
    for s in sorted(recent, key=lambda s: str(s.get("finished_at"))):
        latest[str(s.get("agent"))] = s
    failing = sorted(a for a, s in latest.items() if s.get("status") != "passed")
    value = f"{len(latest) - len(failing)} of {len(latest)} agents passing"
    if failing:
        value += f" (failing: {', '.join(failing)})"
    yield Row(
        "AI",
        "Eval suites passing",
        value,
        "100% of cleared capabilities",
        "breach" if failing else "ok",
        src,
    )


def cost_rows(runs: object, summaries: Sequence[Json], window: Window) -> Iterator[Row]:
    minutes = 0.0
    for run in _records(runs):
        start, stop = _when(run.get("createdAt")), _when(run.get("updatedAt"))
        if start is not None and stop is not None and window.holds(start.date()):
            minutes += max((stop - start).total_seconds(), 0.0) / 60
    yield Row(
        "Cost",
        "Actions wall-clock minutes on main",
        f"{minutes:.0f} min" if runs is not None else "no data",
        "about $100-200 a month",
        "reported" if runs is not None else "no data",
        "runs.json",
    )
    spend = sum(
        _money(s.get("total_cost_usd"))
        for s in summaries
        if not s.get("fake") and (w := _when(s.get("finished_at"))) and window.holds(w.date())
    )
    yield Row(
        "Cost",
        "Real-model eval spend",
        f"${spend:.2f}",
        f"<= ${EVAL_SPEND_MONTHLY:.0f} a month",
        "ok" if spend <= EVAL_SPEND_MONTHLY else "breach",
        "evals/*.json",
    )


# --- assembly ------------------------------------------------------------------------------------


def _summaries(inputs: Path) -> list[Json]:
    folder = inputs / "evals"
    found: list[Json] = []
    for path in sorted(folder.rglob("*.json")) if folder.is_dir() else ():
        value = _load_json(path)
        if isinstance(value, dict) and "agent" in value:
            found.append(cast(Json, value))
    return found


def build(inputs: Path, window: Window, repo: Path = REPO) -> list[Row]:
    runs = _load_json(inputs / "runs.json")
    summaries = _summaries(inputs)
    rows: list[Row] = [
        *ci_rows(runs, window),
        *flow_rows(
            _load_json(inputs / "prs.json"),
            _read(repo / "docs" / "quality" / "escaped-defects.md"),
            _read(repo / "docs" / "product" / "capacity-ledger.md"),
            window,
        ),
        *backfill_rows(_read(repo / "docs" / "quality" / "backfill.md")),
        *coverage_rows(_load_json(inputs / "coverage.json")),
        *mutation_rows(_load_json(inputs / "mutation.json")),
        *authorship_rows(repo),
        *security_rows(repo),
        *contract_rows(repo),
        *journey_rows(_load_json(inputs / "journeys.json")),
        *design_rows(_load_json(inputs / "parity.json")),
        *placeholder_rows(),
        *load_rows(_load_json(inputs / "loadtest-trend.json")),
        *ai_rows(summaries, window),
        *cost_rows(runs, summaries, window),
    ]
    order = {area: i for i, area in enumerate(AREAS)}
    return sorted(rows, key=lambda r: order[r.area])


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(rows: Iterable[Row], window: Window) -> str:
    rows = list(rows)
    lines = [
        f"# Quality report, {window.since.isoformat()} to {window.until.isoformat()}",
        "",
        "Chapter 10 §10.14.2. Generated in Actions; never committed, built or deployed.",
        "",
    ]
    breaches = [r for r in rows if r.status == "breach"]
    lines.append(
        f"**Breaches: {len(breaches)}.** "
        + ("; ".join(f"{r.area}: {r.metric}" for r in breaches) or "None.")
    )
    for area in AREAS:
        lines += ["", f"## {area}", "", "| Metric | Value | Target | Status | Source |"]
        lines.append("|---|---|---|---|---|")
        lines += [
            f"| {_cell(r.metric)} | {_cell(r.value)} | {_cell(r.target)} | {r.status} "
            f"| {_cell(r.source)} |"
            for r in rows
            if r.area == area
        ]
    return "\n".join(lines) + "\n"


def _outside_repo(path: Path, repo: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_relative_to(repo.resolve()):
        raise ReportError(f"{path} is inside the repository; the report is never committed")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.quality.report")
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--since", type=date.fromisoformat)
    parser.add_argument("--until", type=date.fromisoformat)
    parser.add_argument("--out", type=Path, help="markdown file (default: stdout)")
    parser.add_argument("--json", type=Path, dest="json_out", help="rows as JSON")
    args = parser.parse_args(argv)
    until = cast(date | None, args.until) or system_now().date()
    since = cast(date | None, args.since) or until - timedelta(days=13)  # one two-week sprint
    try:
        if since > until:
            raise ReportError("--since is after --until")
        window = Window(since, until)
        rows = build(cast(Path, args.inputs), window)
        text = render_markdown(rows, window)
        if args.out is not None:
            _outside_repo(cast(Path, args.out), REPO).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        if args.json_out is not None:
            payload = {"since": since.isoformat(), "until": until.isoformat()}
            payload_rows = [asdict(r) for r in rows]
            _outside_repo(cast(Path, args.json_out), REPO).write_text(
                json.dumps({**payload, "rows": payload_rows}, indent=2) + "\n", encoding="utf-8"
            )
    except ReportError as exc:
        print(f"quality report: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
