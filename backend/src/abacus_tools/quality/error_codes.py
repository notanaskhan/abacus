"""The error-code catalogue (ADR-139; F-03-T29): `docs/architecture/error-codes.yaml`.

Every conflict (409) and invalid-request (422) code the API can answer with is listed once, with
its status and the classes that raise it. `--write` rebuilds the file from the code; the default
checks that the file and the code agree, so a new code is a catalogue change too.

Run: python -m abacus_tools.quality.error_codes [--write]
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
CATALOGUE = ROOT / "docs" / "architecture" / "error-codes.yaml"

_HEADER = """\
# The error-code catalogue (ADR-139, P-36; F-03-T29). Every 409 and 422 `detail` code the API can
# answer with, its HTTP status and the classes that raise it. Facts beside a code are identifiers
# only (abacus.kernel.errors.check_facts). Rebuild with
# `python -m abacus_tools.quality.error_codes --write`; `make check-fast` checks it.
"""


def _subclasses[C](cls: type[C]) -> list[type[C]]:
    out: list[type[C]] = []
    for sub in cls.__subclasses__():
        out.append(sub)
        out.extend(_subclasses(sub))
    return out


def collect() -> dict[str, dict[str, object]]:
    """Every code in the code, after importing the app (which imports every module)."""
    import abacus.api
    from abacus.kernel.errors import DomainConflict, DomainInvalid

    abacus.api.create_app()  # builds every router, so every module's errors are defined

    statuses: dict[str, set[int]] = {}
    raisers: dict[str, set[str]] = {}
    summaries: dict[str, str] = {}
    bases: tuple[tuple[type[DomainConflict] | type[DomainInvalid], int], ...] = (
        (DomainConflict, 409),
        (DomainInvalid, 422),
    )
    for base, status in bases:
        for cls in [base, *_subclasses(base)]:
            code = cls.code
            statuses.setdefault(code, set()).add(status)
            raisers.setdefault(code, set()).add(f"{cls.__module__}.{cls.__qualname__}")
            # The class's own docstring only: an undocumented class does not inherit its base's.
            own = cls.__dict__.get("__doc__")
            if code not in summaries and cls is not base and isinstance(own, str) and own.strip():
                summaries[code] = inspect.cleandoc(own).split("\n\n")[0].replace("\n", " ")
    codes: dict[str, dict[str, object]] = {}
    for code in sorted(statuses):
        status = statuses[code]
        entry: dict[str, object] = {
            "status": next(iter(status)) if len(status) == 1 else "409 or 422",
            "raised_by": sorted(raisers[code]),
        }
        if code in summaries:
            entry["summary"] = summaries[code]
        codes[code] = entry
    return codes


def render(codes: dict[str, dict[str, object]]) -> str:
    body = yaml.safe_dump({"codes": codes}, sort_keys=False, allow_unicode=True, width=99)
    return _HEADER + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    expected = render(collect())
    if args.write:
        CATALOGUE.write_text(expected, encoding="utf-8")
        return 0
    if not CATALOGUE.exists() or CATALOGUE.read_text(encoding="utf-8") != expected:
        print(f"{CATALOGUE.relative_to(ROOT)} is out of date: run --write and review the diff")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
