"""Connector conformance: run results, unverified fakes and the real-identifier block (A-02-T32;
ADR-044; chapter 10 §10.7.4).

Each provider's suite in `backend/tests/connectors/<provider>/` runs against the fake on every pull
request and against the provider's sandbox nightly (`connectors-nightly.yml`). The nightly job
records both outcomes with `record`; the weekly quality report reads them. When the sandbox fails
while the fake passes, the fake has drifted, and every journey that depends on that fake reads
"unverified" until it is fixed (`unverified`).

`scan` is ADR-044's enforcement: CI blocks a connector recording that holds anything shaped like a
real identifier (a token, a company id outside the synthetic ones, a mailbox outside the reserved
example domains, a phone number outside 555-01xx, the production API host).

    python -m abacus_tools.quality.connector_conformance record --provider quickbooks_online \
        --fake passed --sandbox failed --out connectors.json
    python -m abacus_tools.quality.connector_conformance scan
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Literal, cast

from abacus.kernel.clock import system_now

REPO: Final = Path(__file__).resolve().parents[4]

# Chapter 10 §10.6.6, the fakes each journey needs: who reads "unverified" when a fake drifts.
DEPENDENT_JOURNEYS: Final[dict[str, tuple[str, ...]]] = {
    "quickbooks_online": ("J02", "J05", "J10"),
}
Outcome = Literal["passed", "failed", "skipped"]
OUTCOMES: Final[frozenset[str]] = frozenset({"passed", "failed", "skipped"})

# The company ids synthetic recordings may hold (the fakes', the unit suite's, this suite's).
SYNTHETIC_REALMS: Final[frozenset[str]] = frozenset(
    {"4620816365171234567", "9341453052194873", "1234567890123450"}
)
RECORDING_GLOBS: Final[tuple[str, ...]] = (
    "backend/tests/connectors/*/recordings/*",
    "backend/tests/unit/connections/fixtures/*",
)
_JWT: Final = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.")
_INTUIT_TOKEN: Final = re.compile(r"\bAB11[0-9A-Za-z]{24,}")
_LONG_ID: Final = re.compile(r"(?<![\d.])\d{15,19}(?![\d.])")
_EMAIL: Final = re.compile(r"[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})")
_RESERVED_DOMAINS: Final = ("example.com", "example.org", "example.net")
_RESERVED_SUFFIXES: Final = (".test", ".invalid", ".example", ".localhost")
_PHONE: Final = re.compile(r"(?<!\d)\(?(\d{3})\)?[-. ](\d{3})[-. ](\d{4})(?!\d)")
_PRODUCTION_HOST: Final = re.compile(r"(?<![-.A-Za-z])quickbooks\.api\.intuit\.com")


@dataclass(frozen=True)
class Unverified:
    provider: str
    journeys: tuple[str, ...]


def _providers(results: object) -> dict[str, dict[str, object]]:
    if not isinstance(results, dict):
        return {}
    found = cast(dict[str, object], results).get("providers")
    if not isinstance(found, dict):
        return {}
    return {
        str(k): cast(dict[str, object], v)
        for k, v in cast(dict[str, object], found).items()
        if isinstance(v, dict)
    }


def unverified(results: object) -> list[Unverified]:
    """Every provider whose sandbox failed while its fake passed, with the journeys it makes
    unverified. A skipped sandbox (no credentials) proves nothing either way."""
    out: list[Unverified] = []
    for provider, run in sorted(_providers(results).items()):
        if run.get("fake") == "passed" and run.get("sandbox") == "failed":
            out.append(Unverified(provider, DEPENDENT_JOURNEYS.get(provider, ())))
    return out


def failing_fakes(results: object) -> list[str]:
    """Providers whose fake run failed: the per-PR gate should already have stopped them."""
    return sorted(p for p, run in _providers(results).items() if run.get("fake") == "failed")


def record(
    path: Path, provider: str, fake: Outcome, sandbox: Outcome, now: datetime | None = None
) -> dict[str, object]:
    """Merge one provider's outcomes into the results file (others kept)."""
    if fake not in OUTCOMES or sandbox not in OUTCOMES:
        raise ValueError("an outcome is passed, failed or skipped")
    existing: object = json.loads(path.read_text("utf-8")) if path.is_file() else {}
    providers = _providers(existing)
    providers[provider] = {
        "fake": fake,
        "sandbox": sandbox,
        "finished_at": (now or system_now()).isoformat(),
    }
    document: dict[str, object] = {"providers": dict(sorted(providers.items()))}
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", "utf-8")
    return document


# --- the real-identifier block -------------------------------------------------------------------


def _reserved(domain: str) -> bool:
    domain = domain.lower()
    return (
        domain in _RESERVED_DOMAINS
        or any(domain == d or domain.endswith("." + d) for d in _RESERVED_DOMAINS)
        or domain.endswith(_RESERVED_SUFFIXES)
    )


def findings(text: str) -> list[str]:
    """What in one recording looks like a real identifier; empty when it is clean."""
    found: list[str] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if _JWT.search(line):
            found.append(f"line {n}: a JWT-shaped access token")
        if _INTUIT_TOKEN.search(line):
            found.append(f"line {n}: an Intuit-shaped refresh token")
        for match in _LONG_ID.finditer(line):
            if match.group(0) not in SYNTHETIC_REALMS:
                found.append(f"line {n}: a company id that is not a synthetic realm")
        for match in _EMAIL.finditer(line):
            if not _reserved(match.group(1)):
                found.append(f"line {n}: a mailbox outside the reserved example domains")
        for match in _PHONE.finditer(line):
            if not (match.group(2) == "555" and match.group(3).startswith("01")):
                found.append(f"line {n}: a phone number outside 555-0100..0199")
        if _PRODUCTION_HOST.search(line):
            found.append(f"line {n}: the production QuickBooks API host")
    return found


def recordings(repo: Path = REPO) -> list[Path]:
    paths: set[Path] = set()
    for pattern in RECORDING_GLOBS:
        paths.update(p for p in repo.glob(pattern) if p.is_file())
    return sorted(paths)


def scan(paths: Iterable[Path], repo: Path = REPO) -> list[str]:
    out: list[str] = []
    for path in paths:
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError:
            out.append(f"{path.relative_to(repo)}: not UTF-8 text, so it cannot be checked")
            continue
        out.extend(f"{path.relative_to(repo)}: {f}" for f in findings(text))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="connector_conformance")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--provider", required=True, choices=sorted(DEPENDENT_JOURNEYS))
    rec.add_argument("--fake", required=True, choices=sorted(OUTCOMES))
    rec.add_argument("--sandbox", required=True, choices=sorted(OUTCOMES))
    rec.add_argument("--out", type=Path, required=True)
    sub.add_parser("scan")
    args = parser.parse_args(argv)
    if args.command == "record":
        record(args.out, args.provider, args.fake, args.sandbox)
        for item in unverified(json.loads(args.out.read_text("utf-8"))):
            print(f"{item.provider}: fake drifted; unverified: {', '.join(item.journeys)}")
        return 0
    problems = scan(recordings(REPO), REPO)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
