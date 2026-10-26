"""Release records and gates (Q-01-T11, T18, T34; ADR-088 build once, promote; DEC-54 / P-56).
The workflows call these; nothing here talks to AWS or GitHub: the workflow fetches the facts and
this decides.

    python -m abacus_tools.release manifest apps/web/dist            # prints the manifest SHA-256
    python -m abacus_tools.release record --git-sha <sha> --image-digest sha256:<hex> \
        --spa-manifest-sha256 <hex> --infra-sha <tree sha> --out release.json
    python -m abacus_tools.release check deploy/production/release.json
    python -m abacus_tools.release inspector findings.json            # aws inspector2 output
    python -m abacus_tools.release gate --release deploy/production/release.json \
        --staging-verified staging-verified.json --replay replay.json \
        --inspector inspector.json --current-infra-sha <tree sha>
    python -m abacus_tools.release runtime-config --environment staging --release <sha> \
        --authority <url> --client-id <id> --portal-base-domain <host> [--sentry-dsn <url>]
    python -m abacus_tools.release ops-request deploy/production/ops-requests/<file>.yaml

A release names every deploy input by digest: the image by `sha256:` digest, the SPA by its
manifest's SHA-256, the schema by its Alembic head, the API by the OpenAPI document's SHA-256 and
the infrastructure by its git tree. No tag, no `latest`. A production release adds what its PR
records: an Inspector exception (reason and finding IDs) or the infrastructure applied by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlsplit

import yaml
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
MANIFEST: Final = "manifest.sha256"
RELEASE_KEYS: Final = frozenset(
    {
        "git_sha",
        "image_digest",
        "spa_manifest_sha256",
        "alembic_head",
        "openapi_sha256",
        "infra_sha",
    }
)
OPTIONAL_KEYS: Final = frozenset({"inspector_exception", "infra_applied_sha"})
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9]{4}")
# The operator commands an ops request may name (platform-ops contract 3.5), and nothing else.
OPS_COMMANDS: Final = frozenset(
    {
        "abacus_tools.tenants provision",
        "abacus_tools.tenants status",
        "abacus_tools.tenants key",
        "abacus_tools.tenants entitlement",
        "abacus_tools.platform_control set",
        "abacus_tools.platform_control show",
        "abacus_tools.schedules ensure",
        "abacus_tools.schedules show",
        "abacus_tools.schedules pause",
        "abacus_tools.schedules unpause",
        # P-03-T15 (#419, ED-088): re-render one tenant's pre-masking uploads after a deploy.
        "abacus_tools.trust_layer_backfill",
        # A-02-T12: load the reviewed integration catalogue document (with --dry-run first).
        "abacus_tools.integration_catalog load",
        # Not `abacus_tools.drill verify`: it swaps the production database host, so it runs only
        # from drill.yml with the host of the restore it made (security review, S8 wave B).
    }
)
_HANDLE = re.compile(r"[a-z][a-z0-9._-]{0,60}")


class Refused(Exception):
    """A record or a gate is refused; the message names why (no secret, no data)."""


# --- The SPA manifest --------------------------------------------------------------------------


def write_manifest(dist: Path) -> str:
    """`<sha256>  <path>` for every file under `dist` (sorted, the manifest itself left out),
    written to `dist/manifest.sha256`; returns the manifest's own SHA-256."""
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(dist).as_posix()}"
        for path in sorted(p for p in dist.rglob("*") if p.is_file() and p.name != MANIFEST)
    ]
    body = ("\n".join(lines) + "\n").encode()
    (dist / MANIFEST).write_bytes(body)
    return hashlib.sha256(body).hexdigest()


# --- release.json ------------------------------------------------------------------------------


def alembic_head() -> str:
    """The single head revision of the migrations (`make check-heads` keeps it single)."""
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    if len(heads) != 1:
        raise Refused(f"expected one Alembic head, found {len(heads)}")
    return heads[0]


def openapi_sha256() -> str:
    return hashlib.sha256((REPO / "packages/api-client/openapi.json").read_bytes()).hexdigest()


def record(
    *, git_sha: str, image_digest: str, spa_manifest_sha256: str, infra_sha: str
) -> dict[str, str]:
    found = {
        "git_sha": git_sha,
        "image_digest": image_digest,
        "spa_manifest_sha256": spa_manifest_sha256,
        "alembic_head": alembic_head(),
        "openapi_sha256": openapi_sha256(),
        "infra_sha": infra_sha,
    }
    check(found)
    return found


def check(release: Mapping[str, object], *, production: bool = False) -> None:
    """Refuse anything but the six digests (plus a production release's two recorded facts)."""
    keys = set(release)
    allowed = RELEASE_KEYS | (OPTIONAL_KEYS if production else frozenset[str]())
    if not keys >= RELEASE_KEYS or not keys <= allowed:
        raise Refused(f"release keys must be {sorted(RELEASE_KEYS)}; got {sorted(keys)}")
    rules = {
        "git_sha": _GIT_SHA,
        "image_digest": _DIGEST,
        "spa_manifest_sha256": _SHA256,
        "alembic_head": _REVISION,
        "openapi_sha256": _SHA256,
        "infra_sha": _GIT_SHA,
    }
    for key, rule in rules.items():
        value = release[key]
        if not isinstance(value, str) or not rule.fullmatch(value):
            raise Refused(f"{key} is not a digest of the expected form")
    applied = release.get("infra_applied_sha")
    if applied is not None and (not isinstance(applied, str) or not _GIT_SHA.fullmatch(applied)):
        raise Refused("infra_applied_sha is a git tree SHA")
    exception = release.get("inspector_exception")
    if exception is not None:
        facts: Mapping[str, object] = (
            cast(Mapping[str, object], exception) if isinstance(exception, dict) else {}
        )
        reason, findings = facts.get("reason"), facts.get("finding_ids")
        if (
            not isinstance(reason, str)
            or not 10 <= len(reason) <= 300
            or not isinstance(findings, list)
            or not findings
        ):
            raise Refused("inspector_exception needs a reason (10-300 characters) and finding_ids")


def is_placeholder(release: Mapping[str, object]) -> bool:
    """The committed record before the first production release: nothing to deploy."""
    return release.get("git_sha") is None


# --- Inspector -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class InspectorRecord:
    image_digest: str
    fixable_critical: int
    fixable_high: int
    finding_ids: tuple[str, ...]

    @property
    def promotable(self) -> bool:
        return self.fixable_critical == 0 and self.fixable_high == 0

    def as_json(self) -> str:
        return json.dumps(
            {
                "image_digest": self.image_digest,
                "fixable_critical": self.fixable_critical,
                "fixable_high": self.fixable_high,
                "finding_ids": list(self.finding_ids),
                "promotable": self.promotable,
            },
            sort_keys=True,
        )


def inspector(listing: Mapping[str, object], image_digest: str) -> InspectorRecord:
    """Fixable, active critical and high findings for one image (`aws inspector2 list-findings`
    output). A fix available makes a finding block promotion; one without a fix does not."""
    critical = high = 0
    ids: list[str] = []
    for raw in cast(list[Mapping[str, object]], listing.get("findings", [])):
        if raw.get("status", "ACTIVE") != "ACTIVE" or raw.get("fixAvailable") != "YES":
            continue
        severity = raw.get("severity")
        if severity not in ("CRITICAL", "HIGH"):
            continue
        critical += severity == "CRITICAL"
        high += severity == "HIGH"
        ids.append(str(raw.get("findingArn", "")).rsplit("/", 1)[-1])
    return InspectorRecord(image_digest, critical, high, tuple(sorted(ids)))


# --- The production gate -------------------------------------------------------------------------


def gate(
    release: Mapping[str, object],
    *,
    staging_verified: Mapping[str, object] | None,
    replay: Mapping[str, object] | None,
    inspector_record: Mapping[str, object] | None,
    current_infra_sha: str | None,
    build_record: Mapping[str, object] | None,
) -> list[str]:
    """Why a production release may not deploy; empty when it may. Staging verified this exact
    git SHA and image digest; the SHA's replay tests passed; Inspector found no fixable critical
    or high finding, or the release PR records an exception naming every one; and a changed
    `infra_sha` was applied by hand first (SPEC-050 AC-6); and the record equals the one build.yml
    wrote for the SHA on all six keys."""
    check(release, production=True)
    why: list[str] = []
    # The PR's record is only a pointer: it must be the record build.yml wrote for that SHA, key
    # for key, so a PR cannot name an image, bundle or schema the build never made.
    if build_record is None:
        why.append("build_record_missing")
    elif any(build_record.get(key) != release[key] for key in RELEASE_KEYS):
        why.append("release_differs_from_build")
    sha, digest = release["git_sha"], release["image_digest"]
    if not staging_verified or (
        staging_verified.get("git_sha") != sha
        or staging_verified.get("image_digest") != digest
        or staging_verified.get("smoke") != "passed"
    ):
        why.append("staging_not_verified")
    if not replay or replay.get("git_sha") != sha or replay.get("passed") is not True:
        why.append("replay_not_passed")
    if not inspector_record or inspector_record.get("image_digest") != digest:
        why.append("inspector_missing")
    elif inspector_record.get("promotable") is not True:
        exception = release.get("inspector_exception")
        found = cast(list[str], inspector_record.get("finding_ids") or [])
        listed = (
            cast(list[str], cast(Mapping[str, object], exception).get("finding_ids") or [])
            if isinstance(exception, dict)
            else []
        )
        if not set(found) <= set(listed):
            why.append("inspector_unpromotable")
    changed = current_infra_sha is not None and current_infra_sha != release["infra_sha"]
    if changed and release.get("infra_applied_sha") != release["infra_sha"]:
        why.append("infra_not_applied")
    return why


# --- runtime-config.json (platform-ops contract 3.2) -------------------------------------------


def runtime_config(
    *,
    environment: str,
    release: str,
    authority: str,
    client_id: str,
    portal_base_domain: str,
    sentry_dsn: str | None = None,
) -> dict[str, object]:
    if environment not in ("local", "staging", "production"):
        raise Refused("environment is local, staging or production")
    if not _GIT_SHA.fullmatch(release):
        raise Refused("release is the build's git SHA")
    if urlsplit(authority).scheme != "https" or not client_id:
        raise Refused("oidc needs an https authority and a client ID")
    if not portal_base_domain or "/" in portal_base_domain or ":" in portal_base_domain:
        raise Refused("portal_base_domain is a host name")
    config: dict[str, object] = {
        "environment": environment,
        "oidc": {"authority": authority, "client_id": client_id},
        "release": release,
        "portal_base_domain": portal_base_domain,
    }
    if sentry_dsn:
        config["sentry"] = {"dsn": sentry_dsn, "tunnel": "/v1/telemetry/errors"}
    return config


# --- Production ops requests ---------------------------------------------------------------------


@dataclass(frozen=True)
class OpsRequest:
    command: str
    args: tuple[str, ...]
    operator: str
    reason: str

    def argv(self) -> list[str]:
        module, _, sub = self.command.partition(" ")
        # A command with no subcommand (`abacus_tools.trust_layer_backfill`) passes no empty word.
        return ["python", "-m", module, *([sub] if sub else []), *self.args]


def ops_request(raw: Mapping[str, object]) -> OpsRequest:
    """A `deploy/production/ops-requests/<date>-<slug>.yaml` file: one allowlisted command, its
    arguments, the operator's handle and a reason (no client data). Anything else is refused."""
    if set(raw) != {"command", "args", "operator", "reason"}:
        raise Refused("an ops request has command, args, operator and reason only")
    command, args = raw["command"], raw["args"]
    operator, reason = raw["operator"], raw["reason"]
    if not isinstance(command, str) or command not in OPS_COMMANDS:
        raise Refused("command is not an allowlisted operator command")
    if not isinstance(args, list) or not all(isinstance(a, str) for a in cast(list[object], args)):
        raise Refused("args is a list of strings")
    if not isinstance(operator, str) or not _HANDLE.fullmatch(operator):
        raise Refused("operator is a lower-case handle, never an email address")
    if not isinstance(reason, str) or not 1 <= len(reason) <= 200:
        raise Refused("reason is 1-200 characters")
    return OpsRequest(command, tuple(cast(list[str], args)), operator, reason)


# --- CLI -----------------------------------------------------------------------------------------


def _load(path: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(Path(path).read_text()))


def _optional(path: str | None) -> dict[str, object] | None:
    return _load(path) if path and Path(path).is_file() else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.release")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("manifest").add_argument("dist")
    recording = sub.add_parser("record")
    for name in ("--git-sha", "--image-digest", "--spa-manifest-sha256", "--infra-sha", "--out"):
        recording.add_argument(name, required=True)
    checking = sub.add_parser("check")
    checking.add_argument("release")
    checking.add_argument("--production", action="store_true")
    inspecting = sub.add_parser("inspector")
    inspecting.add_argument("findings")
    inspecting.add_argument("--image-digest", required=True)
    gating = sub.add_parser("gate")
    gating.add_argument("--release", required=True)
    gating.add_argument("--staging-verified")
    gating.add_argument("--replay")
    gating.add_argument("--inspector")
    gating.add_argument("--current-infra-sha")
    gating.add_argument("--build-record")
    config = sub.add_parser("runtime-config")
    for name in ("--environment", "--release", "--authority", "--client-id"):
        config.add_argument(name, required=True)
    config.add_argument("--portal-base-domain", required=True)
    config.add_argument("--sentry-dsn")
    sub.add_parser("ops-request").add_argument("file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "manifest":
            print(write_manifest(Path(args.dist)))
        elif args.command == "record":
            found = record(
                git_sha=args.git_sha,
                image_digest=args.image_digest,
                spa_manifest_sha256=args.spa_manifest_sha256,
                infra_sha=args.infra_sha,
            )
            Path(args.out).write_text(json.dumps(found, sort_keys=True, indent=2) + "\n")
        elif args.command == "check":
            release = _load(args.release)
            if is_placeholder(release):
                print("placeholder")
                return 0
            check(release, production=args.production)
            print("ok")
        elif args.command == "inspector":
            print(inspector(_load(args.findings), args.image_digest).as_json())
        elif args.command == "gate":
            why = gate(
                _load(args.release),
                staging_verified=_optional(args.staging_verified),
                replay=_optional(args.replay),
                inspector_record=_optional(args.inspector),
                current_infra_sha=args.current_infra_sha or None,
                build_record=_optional(args.build_record),
            )
            if why:
                print("refused: " + ", ".join(why), file=sys.stderr)
                return 1
            print("promotable")
        elif args.command == "runtime-config":
            print(
                json.dumps(
                    runtime_config(
                        environment=args.environment,
                        release=args.release,
                        authority=args.authority,
                        client_id=args.client_id,
                        portal_base_domain=args.portal_base_domain,
                        sentry_dsn=args.sentry_dsn,
                    ),
                    sort_keys=True,
                )
            )
        else:
            loaded = cast(dict[str, object], yaml.safe_load(Path(args.file).read_text()))
            print(json.dumps(ops_request(loaded).argv()))
        return 0
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
