"""Fixture JSON from the Python scenario (F-04-T31; F-04.21; ADR-085: one generator).

    make fixtures SNAPSHOT=E0   # python -m abacus_tools.synthetic.fixture_export --snapshot E0

Loads the Brightwater Hale scenario at a named snapshot into a throwaway Postgres (never a
hosted database, never the developer's), calls the API in-process as the scenario's personas on
the MVP read paths, and writes one JSON file per read to
`apps/web/src/fixtures/seed/<snapshot>.<name>.json` (F-04.21: `seed/*.json`). Each file names
the scenario version, its content hash, the snapshot and slices, the persona and the request,
so a fixture always says where it came from. `seed/exported.ts` imports them. The equivalence
test (`tests/integration/test_f04t31_fixture_equivalence.py`) loads the same snapshot, reads the
same paths and requires the committed files to match, and `seed/exported.test.ts` holds
fixture mode to them (with its known gaps pinned).

Reads run under the snapshot's business clock (`clock.frozen`), so `as of` figures are those of
the snapshot. Object keys are sorted and lists keep the API's order.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

import httpx

from abacus.api import create_app
from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, SCENARIO_VERSION
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

REPO: Final = Path(__file__).resolve().parents[4]
EXPORTED: Final = REPO / "apps" / "web" / "src" / "fixtures" / "seed"
SNAPSHOTS: Final = ("E0",)
_IDENTITY_ENV: Final = "ABACUS_IDENTITY_DATABASE_URL"  # the sign-in lookup's database
# The slices the TS seed carries (its portal minimum, with the binders the portal needs): the
# export is `make seed-demo` with `--slice portal`.
SLICES: Final = ("portal",)

Json = object
Resolve = Callable[[Mapping[str, Json]], str]


@dataclass(frozen=True)
class Read:
    """One MVP read path: a name (the file), the persona it is read as, the path (resolved from
    earlier reads where it names an id) and its query."""

    name: str
    persona: str  # a scenario persona slug, e.g. "hannah-leclerc"
    path: str | Resolve
    params: Mapping[str, str] = field(default_factory=dict[str, str])
    label: str = ""  # the request as the fixture handler names it, e.g. "GET /v1/engagements"


def _engagement_of(client: str) -> Resolve:
    """The id of the first engagement (in the API's order) of the client named `client`."""

    def resolve(done: Mapping[str, Json]) -> str:
        rows = done["engagements"]
        if not isinstance(rows, list):
            raise LookupError("engagements")
        for row in cast(list[Json], rows):
            if isinstance(row, dict) and cast(dict[str, Json], row).get("client_name") == client:
                return f"/v1/engagements/{cast(dict[str, Json], row)['id']}/request-items"
        raise LookupError(client)

    return resolve


# The MVP read paths of F-04.21 exported so far (firm personas). The binders index and the portal
# home follow (TASK-1161): the first needs a persona with natural binder access in the load, the
# second a portal sign-in session (ADR-168) minted by the exporter.
READS: Final[tuple[Read, ...]] = (
    Read("firm-clients", "grace-holloway", "/v1/firm/clients", label="GET /v1/firm/clients"),
    Read("engagements", "hannah-leclerc", "/v1/engagements", label="GET /v1/engagements"),
    Read(
        "northwind-request-items",
        "hannah-leclerc",
        _engagement_of("Northwind Robotics, Inc."),
        label="GET /v1/engagements/{engagement_id}/request-items",
    ),
)


def _sorted(value: Json) -> Json:
    """Keys sorted at every level; list order kept (it is the API's order)."""
    if isinstance(value, dict):
        mapping = cast(dict[str, Json], value)
        return {k: _sorted(mapping[k]) for k in sorted(mapping)}
    if isinstance(value, list):
        return [_sorted(v) for v in cast(list[Json], value)]
    return value


async def capture(snapshot: str, *, app_url: str, identity_url: str) -> dict[str, Json]:
    """Every read's body, by name, from a database the scenario was loaded into at `snapshot`.
    The caller has configured nothing; this wires the engine and a fake identity provider and
    puts both back."""
    at = build(snapshot).snapshot.at
    previous_identity = os.environ.get(_IDENTITY_ENV)
    os.environ[_IDENTITY_ENV] = identity_url
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(app_url)
    idp = FakeIdentityProvider()
    configure_verifier(idp.verifier())
    done: dict[str, Json] = {}
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=True)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://fixtures") as http:
            with clock.frozen(at):
                for read in READS:
                    path = read.path if isinstance(read.path, str) else read.path(done)
                    token = idp.token(f"scenario-{read.persona}", mfa=True)
                    headers = {"Authorization": f"Bearer {token}"}
                    response = await http.get(path, params=dict(read.params), headers=headers)
                    if response.status_code != 200:
                        raise RuntimeError(f"{read.name}: {path} answered {response.status_code}")
                    done[read.name] = _sorted(response.json())
    finally:
        reset_verifier()
        await dispose_engine()
        if previous_identity is None:
            os.environ.pop(_IDENTITY_ENV, None)
        else:
            os.environ[_IDENTITY_ENV] = previous_identity
        settings.cache_clear()
        forget_flags()
    return done


def document(snapshot: str, read: Read, body: Json) -> dict[str, Json]:
    """The file's content: where it came from, then the body."""
    return {
        "scenario": {
            "version": SCENARIO_VERSION,
            "hash": SCENARIO_HASH,
            "snapshot": snapshot,
            "slices": list(SLICES),
        },
        "persona": read.persona,
        "request": read.label,
        "body": body,
    }


def file_name(snapshot: str, read: Read) -> str:
    return f"{snapshot.lower()}.{read.name}.json"


def exported_files(out: Path, snapshot: str) -> list[Path]:
    return sorted(out.glob(f"{snapshot.lower()}.*.json"))


def render(snapshot: str, captured: Mapping[str, Json]) -> dict[str, str]:
    """File name -> text, deterministic (two-space indent, sorted keys, trailing newline)."""
    return {
        file_name(snapshot, read): json.dumps(
            document(snapshot, read, captured[read.name]), indent=2, ensure_ascii=False
        )
        + "\n"
        for read in READS
    }


async def _load_and_capture(
    snapshot: str, superuser: str, app: str, identity: str
) -> dict[str, Json]:
    from abacus_tools.synthetic.scenarios.brightwater_hale import loader

    # The loader writes through the app's engine too: point it at the throwaway database first.
    await dispose_engine()
    configure_engine(app)
    try:
        await loader.load(superuser, snapshot, slices=SLICES, wait=False)
    finally:
        await dispose_engine()
    return await capture(snapshot, app_url=app, identity_url=identity)


def export(snapshot: str, out: Path) -> list[Path]:
    """Load `snapshot` into a throwaway Postgres, read the MVP paths and write their files."""
    # Imported here: the throwaway Postgres is only for the command itself.
    from abacus_tools.quality.schema_check import provisioned_database

    with provisioned_database(roundtrip=False) as database:
        captured = asyncio.run(
            _load_and_capture(
                snapshot, database.superuser_dsn, database.app_url, database.identity_url
            )
        )
    out.mkdir(parents=True, exist_ok=True)
    for stale in exported_files(out, snapshot):
        stale.unlink()  # a read no longer exported leaves no file behind
    written: list[Path] = []
    for name, text in render(snapshot, captured).items():
        path = out / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.synthetic.fixture_export")
    parser.add_argument("--snapshot", choices=SNAPSHOTS, default="E0")
    parser.add_argument("--out", type=Path, default=EXPORTED)
    args = parser.parse_args(argv)
    for path in export(args.snapshot, args.out):
        print(f"exported {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
