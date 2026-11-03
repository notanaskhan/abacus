"""Generate `abacus.kernel._provider_terms` from the provider terms register (ADR-114).

Run: python -m abacus_tools.codegen.provider_terms [--check]

The protected `docs/operations/provider-terms.yaml` is validated against ADR-114 (Bedrock only, no
training, named retention exceptions of at most 30 days, a US region, a review within 12 months,
approved by the founder with counsel as the second approver, ADR-114 Q3 and Q-02-T18) and rendered
into a Python literal. The unit tests fail when the
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
    # Q-02-T18 (ADR-114 Q3, Q-02 gate G-2): counsel reviews the entry before the founder approves.
    if entry.get("second_approver") != "counsel":
        raise TermsInvalid("second_approver must be counsel (ADR-114 Q3)")
    approved, review = _date(entry, "approved_on"), _date(entry, "review_by")
    if _date(entry, "second_approved_on") > approved:
        raise TermsInvalid("counsel approves on or before the founder's approved_on")
    if not approved < review <= approved + _MAX_REVIEW:
        raise TermsInvalid("review_by is after approved_on and within 12 months")


_DOCUMENT_ROUTES = frozenset({"textract"})


def validate_document_service(entry: dict[str, object]) -> bool:
    """Register v2 (P-11-T21): a document service entry. A draft needs only its facts; an
    approved one meets the model-route rules too. True when it is approved (compiled in)."""
    if entry.get("route") not in _DOCUMENT_ROUTES:
        raise TermsInvalid("only textract is an eligible document service (ADR-153)")
    status = entry.get("status")
    if status not in ("draft", "approved"):
        raise TermsInvalid("a document service entry is draft or approved")
    if not isinstance(entry.get("ai_services_opt_out"), str):
        raise TermsInvalid("ai_services_opt_out names its evidence")
    basis = entry.get("tri_basis")
    if basis is not None and (not isinstance(basis, str) or not basis.strip()):
        raise TermsInvalid("tri_basis is counsel's words or null")
    if status == "draft":
        if entry.get("approved_on") is not None:
            raise TermsInvalid("a draft entry carries no approval")
        return False
    validate({**entry, "route": "bedrock"})  # the model-route rules, but for its route
    return True


def render(source: str) -> str:
    document = cast(dict[str, object], yaml.safe_load(source) or {})
    entries = cast(list[dict[str, object]], document.get("entries") or [])
    for entry in entries:
        validate(entry)
    lines = [_HEADER]
    lines.append("from abacus.kernel.provider_terms import TermsEntry\n\n")
    services = cast(list[dict[str, object]], document.get("document_services") or [])
    approved = [s for s in services if validate_document_service(s)]
    if (entries or approved) and "from datetime import date\n\n" not in lines:
        lines.insert(1, "from datetime import date\n\n")
    lines.append(f'VERSION = "{hashlib.sha256(source.encode()).hexdigest()}"\n\n')
    lines += _tuple("ENTRIES", entries, kind=None)
    lines.append("\n")
    lines += _tuple("DOCUMENT_SERVICES", approved, kind="document_service")
    return "".join(lines)


def _tuple(name: str, entries: list[dict[str, object]], *, kind: str | None) -> list[str]:
    if not entries:
        return [f"{name}: tuple[TermsEntry, ...] = ()\n"]
    lines = [f"{name}: tuple[TermsEntry, ...] = (\n"]
    for e in entries:
        approved, review = _date(e, "approved_on"), _date(e, "review_by")
        retention = cast(dict[str, object], e["retention"])
        exceptions = [
            (str(x["purpose"]), int(cast(int, x["max_days"])))
            for x in cast(list[dict[str, object]], retention.get("exceptions") or [])
        ]
        subprocessors = [str(x) for x in cast(list[object], e["subprocessors"])]
        lines += [
            "    TermsEntry(\n",
            f"        {_q(e['route'])},\n",
            f"        {_q(e['provider'])},\n",
            f"        {_q(e['region'])},\n",
            f"        date({approved.year}, {approved.month}, {approved.day}),\n",
            f"        date({review.year}, {review.month}, {review.day}),\n",
            f"        material={_q(material(e))},\n",
            "        retention_exceptions=(\n",
            *[f"            ({_q(p)}, {d}),\n" for p, d in exceptions],
            "        ),\n",
            "        subprocessors=(\n",
            *[f"            {_q(x)},\n" for x in subprocessors],
            "        ),\n",
            *(
                [
                    f"        kind={_q(kind)},\n",
                    f"        ai_services_opt_out={_q(e.get('ai_services_opt_out'))},\n",
                    "        tri_basis="
                    + ("None" if e.get("tri_basis") is None else _q(e.get("tri_basis")))
                    + ",\n",
                ]
                if kind
                else []
            ),
            "    ),\n",
        ]
    lines.append(")\n")
    return lines


def material(entry: dict[str, object]) -> str:
    """SPEC-036 Q4: what a firm agrees to. Training, retention, region and subprocessors only."""
    facts = {k: entry.get(k) for k in ("training", "retention", "region", "subprocessors")}
    return hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()


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
