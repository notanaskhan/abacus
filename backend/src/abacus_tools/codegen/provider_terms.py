"""Generate `abacus.kernel._provider_terms` from the provider terms register (ADR-114).

Run: python -m abacus_tools.codegen.provider_terms [--check]

The protected `docs/operations/provider-terms.yaml` is validated against ADR-114 (Bedrock only, no
training, named retention exceptions of at most 30 days, a US region, a review within 12 months,
approved by the founder) and rendered into a Python literal. The unit tests fail when the
checked-in module and the YAML differ; `--check` reports the same without writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
SOURCE = BACKEND.parent / "docs" / "operations" / "provider-terms.yaml"
TARGET = BACKEND / "src" / "abacus" / "kernel" / "_provider_terms.py"
_MAX_RETENTION_DAYS = 30
_MAX_REVIEW = timedelta(days=366)

_HEADER = '''"""GENERATED from docs/operations/provider-terms.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.provider_terms
"""

'''


class TermsInvalid(ValueError):
    pass


def _date(entry: dict[str, object], key: str) -> date:
    value = entry.get(key)
    if not isinstance(value, date):
        raise TermsInvalid(f"{key} must be a date (YYYY-MM-DD)")
    return value


def validate(entry: dict[str, object]) -> None:
    """ADR-114 §1: refuse an entry that doesn't meet every condition."""
    if entry.get("route") != "bedrock":
        raise TermsInvalid("only the bedrock route may carry client data (ADR-113)")
    for key in ("provider", "region", "breach_notice"):
        if not isinstance(entry.get(key), str) or not cast(str, entry[key]).strip():
            raise TermsInvalid(f"{key} is required")
    if not cast(str, entry["region"]).startswith("us-"):
        raise TermsInvalid("processing must be in a US region (ADR-021)")
    documents = entry.get("documents")
    if not isinstance(documents, list) or not documents:
        raise TermsInvalid("documents are required")
    for document in cast(list[dict[str, object]], documents):
        if not document.get("title") or not document.get("version"):
            raise TermsInvalid("each document needs a title and version")
        _date(document, "accepted_on")
    if entry.get("training") != "none":
        raise TermsInvalid("training must be none")
    retention = entry.get("retention")
    if not isinstance(retention, dict):
        raise TermsInvalid("retention is required")
    retention = cast(dict[str, object], retention)
    if retention.get("beyond_processing") is not False:
        raise TermsInvalid("prompts and outputs may not be stored beyond processing")
    for exception in cast(list[dict[str, object]], retention.get("exceptions") or []):
        days = exception.get("max_days")
        if not exception.get("purpose") or not isinstance(days, int):
            raise TermsInvalid("each retention exception needs a purpose and max_days")
        if days > _MAX_RETENTION_DAYS:
            raise TermsInvalid(f"retention exceptions are at most {_MAX_RETENTION_DAYS} days")
    if not isinstance(entry.get("subprocessors"), list):
        raise TermsInvalid("subprocessors must be a list")
    if entry.get("approved_by") != "founder":
        raise TermsInvalid("approved_by must be founder (ADR-114 Q3)")
    approved, review = _date(entry, "approved_on"), _date(entry, "review_by")
    if not approved < review <= approved + _MAX_REVIEW:
        raise TermsInvalid("review_by is after approved_on and within 12 months")


def render(source: str) -> str:
    document = cast(dict[str, object], yaml.safe_load(source) or {})
    entries = cast(list[dict[str, object]], document.get("entries") or [])
    for entry in entries:
        validate(entry)
    lines = [_HEADER]
    if entries:
        lines.append("from datetime import date\n\n")
    lines.append("from abacus.kernel.provider_terms import TermsEntry\n\n")
    lines.append(f'VERSION = "{hashlib.sha256(source.encode()).hexdigest()}"\n\n')
    if not entries:
        lines.append("ENTRIES: tuple[TermsEntry, ...] = ()\n")
        return "".join(lines)
    lines.append("ENTRIES: tuple[TermsEntry, ...] = (\n")
    for e in entries:
        approved, review = _date(e, "approved_on"), _date(e, "review_by")
        lines += [
            "    TermsEntry(\n",
            f"        {_q(e['route'])},\n",
            f"        {_q(e['provider'])},\n",
            f"        {_q(e['region'])},\n",
            f"        date({approved.year}, {approved.month}, {approved.day}),\n",
            f"        date({review.year}, {review.month}, {review.day}),\n",
            "    ),\n",
        ]
    lines.append(")\n")
    return "".join(lines)


def _q(value: object) -> str:
    return json.dumps(str(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the module is out of date")
    args = parser.parse_args(argv)
    expected = render(SOURCE.read_text())
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != expected:
            print(f"{TARGET.relative_to(BACKEND)} is out of date with {SOURCE.name}")
            return 1
        return 0
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
