"""The fakes register check (Q-03-T094): which provider fakes are unverified.

    python -m abacus_tools.quality.fakes [--strict]

Reads `docs/quality/fakes.yaml`. A fake is unverified when it has never been checked against its
provider's sandbox, or not within `max_age_days`. Every listed fake and suite must exist. Prints
the unverified ones; `--strict` (for the quarter's end) fails while any is unverified.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import yaml

from abacus.kernel.clock import system_now

REPO = Path(__file__).resolve().parents[4]
REGISTER = REPO / "docs" / "quality" / "fakes.yaml"


@dataclass(frozen=True)
class Fake:
    fake: str
    provider: str
    suite: str
    verified_on: date | None


def load(path: Path = REGISTER) -> tuple[int, list[Fake]]:
    raw = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    rows = cast(list[dict[str, object]], raw["fakes"])
    fakes = [
        Fake(
            str(r["fake"]),
            str(r["provider"]),
            str(r["suite"]),
            r["verified_on"] if isinstance(r.get("verified_on"), date) else None,  # pyright: ignore[reportArgumentType] -- yaml reads ISO dates as date
        )
        for r in rows
    ]
    return int(cast(int, raw["max_age_days"])), fakes


def problems(fakes: list[Fake], root: Path = REPO) -> list[str]:
    out: list[str] = []
    for f in fakes:
        out += [f"{p} does not exist" for p in (f.fake, f.suite) if not (root / p).exists()]
    return out


def unverified(fakes: list[Fake], today: date, max_age_days: int) -> list[Fake]:
    oldest = today - timedelta(days=max_age_days)
    return [f for f in fakes if f.verified_on is None or f.verified_on < oldest]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    max_age, fakes = load()
    broken = problems(fakes)
    stale = unverified(fakes, system_now().date(), max_age)
    for p in broken:
        print(p)
    for f in stale:
        print(f"unverified: {f.fake} ({f.provider})")
    print(f"{len(stale)} of {len(fakes)} fakes unverified")
    return 1 if broken or (args.strict and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
