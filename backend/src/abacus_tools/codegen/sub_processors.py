"""Validate the sub-processor register and generate its Markdown (P-67, ADR-154; Q-01-T51).

Run: python -m abacus_tools.codegen.sub_processors [--check]

Source: docs/operations/sub-processors.yaml. Output: docs/operations/sub-processors.md, the table
for the vendor-diligence pack. The register is valid only when every egress host written in
`infra/**/*.tf` has a row: the strings in a `domains = [...]` list (the DNS Firewall allowlist) or
in any `*_domains` / `*_hosts` list. A row covers a host when one of its `egress_hosts` equals it,
or is `*.<suffix>` and the host ends in `.<suffix>`.

`--check` (in `make check-generated`) fails when the Markdown is stale, a row is malformed or an
egress host has no row.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
SOURCE = ROOT / "docs" / "operations" / "sub-processors.yaml"
TARGET = ROOT / "docs" / "operations" / "sub-processors.md"
INFRA = ROOT / "infra"
ADR_DIR = ROOT / "docs" / "adr"

KINDS = ("sub-processor", "integration", "operations", "egress-only")
KIND_TITLES = {
    "sub-processor": "Sub-processors",
    "integration": "Customer-authorised integrations (not sub-processors)",
    "operations": "Accrued's own operations (no client data)",
    "egress-only": "Egress only (no data sent)",
}
DPA_STATUSES = ("to-confirm", "signed", "not-required")
FIELDS = (
    "id",
    "party",
    "service",
    "kind",
    "role",
    "data_seen",
    "client_data",
    "region",
    "dpa",
    "needed_by",
    "egress_hosts",
    "references",
)
_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_HOST = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")
_REFERENCE = re.compile(r"^(ADR-\d{3}|DEC-\d{2,3})$")
# Terraform lists that name egress hosts, and the plain string literals inside one.
_TF_HOST_LIST = re.compile(r"\b(?:domains|\w+_domains|\w+_hosts)\s*=\s*\[(.*?)\]", re.S)
_TF_STRING = re.compile(r'"([^"$]*)"')


class RegisterError(ValueError):
    pass


@dataclass(frozen=True)
class Row:
    id: str
    party: str
    service: str
    kind: str
    role: str
    data_seen: str
    client_data: bool
    region: str
    dpa: str
    needed_by: str
    egress_hosts: tuple[str, ...]
    references: tuple[str, ...]


def parse(source: str) -> list[Row]:
    """Every row, validated."""
    document = cast(dict[str, object], yaml.safe_load(source) or {})
    raw = cast(list[dict[str, object]], document.get("rows") or [])
    if not raw:
        raise RegisterError("no rows")
    rows: list[Row] = []
    seen: set[str] = set()
    for index, fields in enumerate(raw):
        where = str(fields.get("id", f"row {index + 1}"))
        missing = [f for f in FIELDS if f not in fields]
        if missing:
            raise RegisterError(f"{where}: missing {missing}")
        unknown = sorted(set(fields) - set(FIELDS))
        if unknown:
            raise RegisterError(f"{where}: unknown fields {unknown}")
        if not _ID.fullmatch(where) or where in seen:
            raise RegisterError(f"{where}: an id is kebab-case and unique")
        seen.add(where)
        if fields["kind"] not in KINDS:
            raise RegisterError(f"{where}: kind {fields['kind']!r} is not one of {KINDS}")
        if fields["dpa"] not in DPA_STATUSES:
            raise RegisterError(f"{where}: dpa {fields['dpa']!r} is not one of {DPA_STATUSES}")
        if not isinstance(fields["client_data"], bool):
            raise RegisterError(f"{where}: client_data is true or false")
        if (
            fields["client_data"]
            and fields["dpa"] == "not-required"
            and fields["kind"] != "integration"
        ):
            raise RegisterError(f"{where}: a party that sees client data needs a DPA")
        text = ("party", "service", "role", "data_seen", "region", "needed_by")
        for name in text:
            if not isinstance(fields[name], str) or not str(fields[name]).strip():
                raise RegisterError(f"{where}: {name} is a non-empty string")
        hosts = cast(list[object], fields["egress_hosts"] or [])
        for host in hosts:
            if not isinstance(host, str) or not _HOST.fullmatch(host):
                raise RegisterError(f"{where}: egress host {host!r} is a lower-case host name")
        references = cast(list[object], fields["references"] or [])
        for reference in references:
            if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
                raise RegisterError(f"{where}: reference {reference!r} is ADR-nnn or DEC-nn")
            if reference.startswith("ADR-") and not any(ADR_DIR.glob(f"{reference}-*.md")):
                raise RegisterError(f"{where}: {reference} does not exist in docs/adr")
        rows.append(
            Row(
                id=where,
                party=str(fields["party"]),
                service=str(fields["service"]),
                kind=str(fields["kind"]),
                role=str(fields["role"]),
                data_seen=str(fields["data_seen"]),
                client_data=bool(fields["client_data"]),
                region=str(fields["region"]),
                dpa=str(fields["dpa"]),
                needed_by=str(fields["needed_by"]),
                egress_hosts=tuple(str(h) for h in hosts),
                references=tuple(str(r) for r in references),
            )
        )
    return rows


def terraform_egress_hosts(infra: Path) -> dict[str, list[str]]:
    """Each egress host written in `infra/**/*.tf`, with the files that name it."""
    found: dict[str, list[str]] = {}
    for path in sorted(infra.rglob("*.tf")):
        if ".terraform" in path.parts:
            continue
        text = re.sub(r"(?m)^\s*(#|//).*$", "", path.read_text(encoding="utf-8"))
        for block in _TF_HOST_LIST.finditer(text):
            for literal in _TF_STRING.findall(block.group(1)):
                host = literal.strip().lower().rstrip(".")
                if host:
                    found.setdefault(host, []).append(str(path.relative_to(infra.parent)))
    return found


def covers(pattern: str, host: str) -> bool:
    if pattern == host:
        return True
    return pattern.startswith("*.") and host.endswith(pattern[1:])


def unregistered(rows: list[Row], hosts: dict[str, list[str]]) -> list[str]:
    """Egress hosts in Terraform that no row covers, with where they are written."""
    patterns = [p for row in rows for p in row.egress_hosts]
    return [
        f"{host} ({', '.join(sorted(set(files)))})"
        for host, files in sorted(hosts.items())
        if not any(covers(p, host) for p in patterns)
    ]


def _cell(value: str) -> str:
    return value.replace("|", "\\|")


def render(rows: list[Row]) -> str:
    lines = [
        "<!-- GENERATED from docs/operations/sub-processors.yaml. Do not edit. -->",
        "<!-- Regenerate: python -m abacus_tools.codegen.sub_processors -->",
        "",
        "# Sub-processors",
        "",
        "Every party that runs part of Accrued or that our network reaches (P-67, ADR-154).",
        "Client data stays in Accrued's AWS account, in the US. DPA status only, no terms.",
    ]
    for kind in KINDS:
        members = [r for r in rows if r.kind == kind]
        if not members:
            continue
        lines += [
            "",
            f"## {KIND_TITLES[kind]}",
            "",
            "| Party | Service | Role | Data seen | Client data | Region | DPA | Needed by |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in members:
            cells = (
                r.party,
                r.service,
                r.role,
                r.data_seen,
                "yes" if r.client_data else "no",
                r.region,
                r.dpa,
                r.needed_by,
            )
            lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sub_processors")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = parse(SOURCE.read_text(encoding="utf-8"))
    except RegisterError as exc:
        print(f"sub-processors.yaml: {exc}", file=sys.stderr)
        return 1
    missing = unregistered(rows, terraform_egress_hosts(INFRA))
    for host in missing:
        print(f"sub-processors.yaml: egress host {host} has no register row", file=sys.stderr)
    if missing:
        return 1
    text = render(rows)
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            print(f"{TARGET.relative_to(ROOT)} is out of date", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
