"""The tax-year rollover's drafts (T-03-T18; DEC-76, P-62; K-02 §4.3).

    python -m abacus_tools.refdata_rollover --key us-form-8879-set-ty2026 --kind form_8879_set \
        --to-year 2027 --as-of 2026-12-01 --out ~/accrued-ops/refdata/ty2027
    python -m abacus_tools.refdata_rollover --kind legal_holidays --to-year 2028 \
        --out ~/accrued-ops/refdata/ty2027

Writes a **draft** payload for people to review, never a published row: the operator then runs
`abacus_tools.refdata draft` on the reviewed file and a second person publishes it (two-person,
K-02). It refuses to write anywhere inside the repository, because reference content never lands
in a commit (DEC-76; the one exception is a module's parameter file).

- `due_date_rules`: the rules are offsets from the period end, so the rows carry over unchanged;
  the reviewer confirms none changed in law for the new year.
- `form_8879_set`: each row's `tax_year` moves to the new year; the revisions and the Pub 1345
  tolerances carry over **marked for re-verification**, never defaulted (DEC-85).
- `information_return_thresholds`: each row's `payment_year` moves; amounts carry over for review.
- `legal_holidays`: computed for the year from 5 U.S.C. 6103 (federal) and D.C. Code § 1-612.02
  (DC Emancipation Day; Inauguration Day in an inauguration year), each at its observed date when
  it falls on a weekend (Saturday to Friday, Sunday to Monday).

Every draft carries a `review` block naming what a person must check before it is drafted.
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Final, cast

from abacus_tools.refdata import Refused, current_payload

REPO: Final = Path(__file__).resolve().parents[3]
ROLLED: Final = ("due_date_rules", "form_8879_set", "information_return_thresholds")
KINDS: Final = (*ROLLED, "legal_holidays")
REVIEW: Final[dict[str, tuple[str, ...]]] = {
    "due_date_rules": (
        "Each form's original and extended due date rule is unchanged in law for the new year.",
        "Estimated-tax installment months (1040-ES, 1041-ES, 1120-W) are unchanged.",
    ),
    "form_8879_set": (
        "Each return type's authorization form and revision for the new year (IRS e-file forms).",
        "Pub 1345's relock tolerances re-verified for the season (DEC-85: never defaulted).",
    ),
    "information_return_thresholds": (
        "Each form's reporting threshold and minimum count for the payment year (IRS form"
        " instructions).",
    ),
    "legal_holidays": (
        "Each date against OPM's federal holiday schedule and the DC government's holiday list.",
        "Any holiday added or moved by statute or proclamation for the year.",
        "A Saturday January 1 is observed on the prior December 31, which sits in this set.",
    ),
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def observed(day: date) -> date:
    """Saturday is observed on Friday, Sunday on Monday (5 U.S.C. 6103(b); EO 11582)."""
    if day.weekday() == calendar.SATURDAY:
        return day - timedelta(days=1)
    if day.weekday() == calendar.SUNDAY:
        return day + timedelta(days=1)
    return day


def holidays(year: int) -> list[dict[str, object]]:
    """The year's federal and DC legal holidays as `legal_holidays` rows, by date."""
    fixed = (
        (date(year, 1, 1), "New Year's Day", "US"),
        (date(year, 6, 19), "Juneteenth National Independence Day", "US"),
        (date(year, 7, 4), "Independence Day", "US"),
        (date(year, 11, 11), "Veterans Day", "US"),
        (date(year, 12, 25), "Christmas Day", "US"),
        (date(year, 4, 16), "DC Emancipation Day", "DC"),
    )
    floating = (
        (_nth_weekday(year, 1, calendar.MONDAY, 3), "Birthday of Martin Luther King, Jr.", "US"),
        (_nth_weekday(year, 2, calendar.MONDAY, 3), "Washington's Birthday", "US"),
        (_last_weekday(year, 5, calendar.MONDAY), "Memorial Day", "US"),
        (_nth_weekday(year, 9, calendar.MONDAY, 1), "Labor Day", "US"),
        (_nth_weekday(year, 10, calendar.MONDAY, 2), "Columbus Day", "US"),
        (_nth_weekday(year, 11, calendar.THURSDAY, 4), "Thanksgiving Day", "US"),
    )
    rows: list[tuple[date, str, str]] = []
    for day, name, where in fixed:
        moved = observed(day)
        rows.append((moved, name if moved == day else f"{name} (observed)", where))
    rows += list(floating)
    # Inauguration Day (5 U.S.C. 6103(c)), a DC-area holiday every fourth year from 1965; on a
    # Sunday it moves to the Monday.
    if (year - 1965) % 4 == 0:
        inauguration = date(year, 1, 20)
        if inauguration.weekday() == calendar.SUNDAY:
            inauguration += timedelta(days=1)
        rows.append((inauguration, "Inauguration Day", "DC"))
    return [{"date": d.isoformat(), "name": n, "jurisdiction": j} for d, n, j in sorted(rows)]


def roll(kind: str, payload: Mapping[str, object], to_year: int) -> dict[str, object]:
    """The draft for `to_year` from the version in effect (`legal_holidays` is computed)."""
    if kind not in ROLLED:
        raise Refused(f"{kind} isn't rolled from a prior version")
    if payload.get("kind") != kind:
        raise Refused(f"the version in effect is {payload.get('kind')!r}, not {kind}")
    rows = [dict(r) for r in cast(Sequence[Mapping[str, object]], payload.get("rows", []))]
    if kind == "form_8879_set":
        rows = [{**r, "tax_year": to_year} for r in rows]
    elif kind == "information_return_thresholds":
        rows = [{**r, "payment_year": to_year} for r in rows]
    out: dict[str, object] = {"kind": kind, "rows": rows}
    if kind == "form_8879_set":
        out["tolerances"] = payload.get("tolerances")
    return out


def _outside_repo(out: Path) -> Path:
    resolved = out.expanduser().resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise Refused("drafts are reference content: write them outside the repository (DEC-76)")
    return resolved


def write_draft(
    out: Path, kind: str, to_year: int, payload: Mapping[str, object], source: str | None
) -> Path:
    """The draft file and its review block (the `review` key is dropped before `refdata draft`)."""
    folder = _outside_repo(out)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{kind}-{to_year}.draft.json"
    body = {
        **payload,
        "review": {
            "status": "draft: needs review before `refdata draft`",
            "rolled_from": source,
            "check": list(REVIEW[kind]),
        },
    }
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


async def _main(args: argparse.Namespace) -> Path:
    kind, to_year = cast(str, args.kind), cast(int, args.to_year)
    if kind == "legal_holidays":
        return write_draft(
            args.out, kind, to_year, {"kind": kind, "rows": holidays(to_year)}, None
        )
    if not args.key:
        raise Refused(f"{kind} rolls from a published version: name it with --key")
    as_of = date.fromisoformat(cast(str, args.as_of)) if args.as_of else date.today()
    current = await current_payload(cast(str, args.key), as_of)
    if current is None:
        raise Refused(f"no version of {args.key} is in effect on {as_of.isoformat()}")
    return write_draft(args.out, kind, to_year, roll(kind, current, to_year), cast(str, args.key))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.refdata_rollover")
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--key")
    parser.add_argument("--as-of")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(asyncio.run(_main(args)))
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
