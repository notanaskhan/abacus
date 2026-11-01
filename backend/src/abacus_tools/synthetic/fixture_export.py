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

Each exported snapshot has a profile (`PROFILES`): its slices, flags and reads. E0 is the MVP
paths above; `2026-09-24T10:20` is A-03's AUD-11 and AUD-31 (DEC-1770). Its reads answer ids
the server makes (work items, sample sets, mapping sets, FS lines …), so `server_ids` names each
by its natural key after the load, and the files carry `stable_id(key)` in its place, inside
strings too, with each content hash remade from its object's stand-in: two loads export the
same bytes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import uuid
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
from abacus.modules.identity.api import (
    configure_verifier,
    issue_sign_in_code,
    reset_verifier,
    totp_at,
)
from abacus_tools.db_connect import connect
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, SCENARIO_VERSION
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import TENANT
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

REPO: Final = Path(__file__).resolve().parents[4]
EXPORTED: Final = REPO / "apps" / "web" / "src" / "fixtures" / "seed"
_IDENTITY_ENV: Final = "ABACUS_IDENTITY_DATABASE_URL"  # the sign-in lookup's database
# The slices the TS seed carries (its portal minimum, with the binders the portal needs): the
# export is `make seed-demo` with `--slice portal`.
SLICES: Final = ("portal", "tax_board", "standards")  # T-02-T11 the board; K-02-T18 KNW-04
# The flags the exported reads stand behind, on in the throwaway tenant as fixture mode has them:
# the binders index (P-06) and the portal's sign-in and home (P-08).
FLAGS: Final = (
    "binders.engine",
    "portal.sign_in_v2",
    "portal.home_v2",
    "tax.returns_v1",
    "knowledge.firm_standards",  # K-02-T18: KNW-04's standards
)
# Portals are served at `<slug>.<portal_base_domain>`; the local runtime config's domain.
PORTAL_BASE_DOMAIN: Final = "portal.localhost"
PORTAL_HOST: Final = f"brightwaterhale.{PORTAL_BASE_DOMAIN}"
PORTAL_SINK: Final = "sink.brightwaterhale.test"  # the scenario's client people's mail domain
_PORTAL_ENV: Final = "ABACUS_PORTAL_BASE_DOMAIN"

Json = object
# A read's path from the reads before it and the server-made ids found after the load, by their
# stand-in labels (`server_ids`).
Resolve = Callable[[Mapping[str, Json], Mapping[str, str]], str]


@dataclass(frozen=True)
class Read:
    """One MVP read path: a name (the file), the persona it is read as, the path (resolved from
    earlier reads where it names an id) and its query."""

    name: str
    persona: str  # a scenario persona slug, e.g. "hannah-leclerc"
    path: str | Resolve
    params: Mapping[str, str] = field(default_factory=dict[str, str])
    label: str = ""  # the request as the fixture handler names it, e.g. "GET /v1/engagements"
    portal: bool = False  # read as a client on the firm's portal host, through a portal session


def _engagement_of(client: str) -> Resolve:
    """The id of the first engagement (in the API's order) of the client named `client`."""

    def resolve(done: Mapping[str, Json], _: Mapping[str, str]) -> str:
        rows = done["engagements"]
        if not isinstance(rows, list):
            raise LookupError("engagements")
        for row in cast(list[Json], rows):
            if isinstance(row, dict) and cast(dict[str, Json], row).get("client_name") == client:
                return f"/v1/engagements/{cast(dict[str, Json], row)['id']}/request-items"
        raise LookupError(client)

    return resolve


# The MVP read paths of F-04.21. The binders index is read by Daniel Reyes, the Feld engagement's
# partner (a membership the load writes; the practice leader's `in_scope` reads nothing until
# practice lines load, and the P-06-T29 golden's Grace has a membership granted by hand); the
# portal home by Claire Feld, through a portal session the exporter signs her in for (ADR-168).
READS: Final[tuple[Read, ...]] = (
    Read("firm-clients", "grace-holloway", "/v1/firm/clients", label="GET /v1/firm/clients"),
    Read("engagements", "hannah-leclerc", "/v1/engagements", label="GET /v1/engagements"),
    # T-02-T11: TAX-01's tiles and rows as Grace (firm admin) sees the TY2025 board.
    Read(
        "tax-returns-summary",
        "grace-holloway",
        "/v1/tax-returns/summary",
        label="GET /v1/tax-returns/summary",
    ),
    Read("tax-returns", "grace-holloway", "/v1/tax-returns", label="GET /v1/tax-returns"),
    # K-02-T18: KNW-04's section rows as Priya Raman (a partner: she sees the 1040 v7 draft).
    Read("standards", "priya-raman", "/v1/standards", label="GET /v1/standards"),
    Read(
        "northwind-request-items",
        "hannah-leclerc",
        _engagement_of("Northwind Robotics, Inc."),
        label="GET /v1/engagements/{engagement_id}/request-items",
    ),
    Read(
        "binders",
        "daniel-reyes",
        "/v1/binders",
        {"service": "tax_returns", "season": "TY2025"},
        label="GET /v1/binders",
    ),
    Read(
        "portal-home", "claire-feld", "/v1/portal/home", label="GET /v1/portal/home", portal=True
    ),
)


# A-03-T16 (TASK-2719; DEC-1770): AUD-11 and AUD-31 at AUD-11 f's clock, with the `sampling` slice
# alone (it brings people, standards and acceptance): Northwind's Participants as Marcus Delaney
# (AUD-11 a), Granite Peak's Disbursements as Simone Baptiste (AUD-11 f) and Granite Peak's
# mapping as Caleb Dunn (AUD-31 f). Work items, sets, versions, populations and mapping sets are
# the server's ids; each path names its id by stand-in label.
SAMPLING_SNAPSHOT: Final = "2026-09-24T10:20"
_NW: Final = "northwind"
_GP: Final = "granite"


def _path(template: str, *labels: str) -> Resolve:
    """`template` with each `{n}` the raw id of the n-th stand-in label."""

    def resolve(_: Mapping[str, Json], found: Mapping[str, str]) -> str:
        missing = [label for label in labels if label not in found]
        if missing:
            raise LookupError(f"no server id for {missing}")
        return template.format(*(found[label] for label in labels))

    return resolve


def _sampling_reads() -> tuple[Read, ...]:
    from abacus_tools.synthetic.scenarios.brightwater_hale.audits import BY_LABEL
    from abacus_tools.synthetic.scenarios.brightwater_hale.loader import engagement_id_of

    nw, gp = (str(engagement_id_of(BY_LABEL[label])) for label in ("A1", "A2"))
    sets = [
        (_NW, "marcus-delaney", nw, "Participants", 2),
        (_GP, "simone-baptiste", gp, "Disbursements", 1),
    ]
    reads: list[Read] = []
    for slug, persona, engagement, title, version in sets:
        item = f"work-item:{engagement}"
        sample_set = f"sample-set:{title}"
        reads += [
            Read(
                f"{slug}-sample-sets",
                persona,
                _path("/v1/work-items/{0}/sample-sets", item),
                label="GET /v1/work-items/{work_item_id}/sample-sets",
            ),
            Read(
                f"{slug}-{title.lower()}",
                persona,
                _path("/v1/sample-sets/{0}", sample_set),
                label="GET /v1/sample-sets/{sample_set_id}",
            ),
            Read(
                f"{slug}-{title.lower()}-v{version}-items",
                persona,
                _path(f"/v1/sample-sets/{{0}}/versions/{version}/items", sample_set),
                label="GET /v1/sample-sets/{sample_set_id}/versions/{version_no}/items",
            ),
            Read(
                f"{slug}-{title.lower()}-v{version}-population",
                persona,
                _path("/v1/populations/{0}", f"population-of:{title}:{version}"),
                label="GET /v1/populations/{population_id}",
            ),
        ]
    reads += [
        Read(
            "granite-mapping-sets",
            "caleb-dunn",
            f"/v1/engagements/{gp}/mapping-sets",
            label="GET /v1/engagements/{engagement_id}/mapping-sets",
        ),
        Read(
            "granite-mapping",
            "caleb-dunn",
            _path("/v1/mapping-sets/{0}", f"mapping-set:{gp}"),
            label="GET /v1/mapping-sets/{mapping_set_id}",
        ),
    ]
    return tuple(reads)


# Server-made ids and the natural key each one's stand-in is made from (`stable_id(label)`). A
# label may name another server id; `server_ids` puts that id's label in its place.
_SERVER_IDS: Final = (
    "SELECT w.id, 'work-item:' || w.engagement_id FROM work_items w "
    "WHERE w.tenant_id = $1 AND w.kind = 'assurance'",
    "SELECT id, 'sample-set:' || title FROM sample_sets WHERE tenant_id = $1",
    "SELECT v.id, 'sample-set-version:' || s.title || ':' || v.version_no "
    "FROM sample_set_versions v JOIN sample_sets s ON s.id = v.sample_set_id "
    "WHERE v.tenant_id = $1",
    "SELECT v.population_id, 'population-of:' || s.title || ':' || v.version_no "
    "FROM sample_set_versions v JOIN sample_sets s ON s.id = v.sample_set_id "
    "WHERE v.tenant_id = $1",
    "SELECT t.id, 'tie:' || t.population_id || ':' || t.position FROM completeness_ties t "
    "WHERE t.tenant_id = $1",
    "SELECT id, 'mapping-set:' || engagement_id FROM mapping_sets WHERE tenant_id = $1",
    "SELECT id, 'grouping-set:' || key FROM grouping_sets WHERE tenant_id = $1",
    "SELECT v.id, 'grouping-set-version:' || s.key || ':' || v.version "
    "FROM grouping_set_versions v JOIN grouping_sets s ON s.id = v.grouping_set_id "
    "WHERE v.tenant_id = $1",
    "SELECT id, 'grouping:' || version_id || ':' || key FROM groupings WHERE tenant_id = $1",
    "SELECT id, 'fs-line:' || version_id || ':' || key FROM fs_lines WHERE tenant_id = $1",
    "SELECT id, 'trial-balance:' || engagement_id FROM trial_balances WHERE tenant_id = $1",
    "SELECT id, 'tb-version:' || trial_balance_id || ':' || version_no "
    "FROM trial_balance_versions WHERE tenant_id = $1",
    "SELECT id, 'ledger-snapshot:' || client_entity_id || ':' || period_end || ':' || "
    "raw_fingerprint FROM ledger_snapshots WHERE tenant_id = $1",
    "SELECT id, 'gl-snapshot:' || client_entity_id || ':' || kind || ':' || period_start "
    "FROM gl_snapshots WHERE tenant_id = $1",
    "SELECT v.id, 'evidence-version:' || i.engagement_id || ':' || i.title || ':' || "
    "v.version_no FROM evidence_versions v JOIN evidence_items i ON i.id = v.evidence_item_id "
    "WHERE v.tenant_id = $1",
    "SELECT id, 'evidence-item:' || engagement_id || ':' || title FROM evidence_items "
    "WHERE tenant_id = $1",
    "SELECT id, 'sign-off:' || target_type || ':' || target_id || ':' || level || ':' || "
    "created_at FROM sign_offs WHERE tenant_id = $1",
)
_HASH_KEYS: Final = frozenset({"content_hash", "seen_hash"})


@dataclass(frozen=True)
class Profile:
    """What a snapshot's export loads and reads."""

    slices: tuple[str, ...]
    flags: tuple[str, ...]
    reads: tuple[Read, ...]
    server_ids: bool = False  # the reads answer server-made ids, swapped for stand-ins


PROFILES: Final[dict[str, Profile]] = {
    "E0": Profile(SLICES, FLAGS, READS),
    SAMPLING_SNAPSHOT: Profile(("sampling",), (), _sampling_reads(), server_ids=True),
}
SNAPSHOTS: Final = tuple(PROFILES)


async def server_ids(snapshot: str, superuser: str) -> dict[str, str]:
    """Raw server id -> stand-in label, after the load (empty where the profile has none). A
    label's own server ids are replaced by their labels, so every label is a natural key."""
    if not PROFILES[snapshot].server_ids:
        return {}
    conn = await connect(superuser)
    try:
        labels: dict[str, str] = {}
        for sql in _SERVER_IDS:
            for row in await conn.fetch(sql, TENANT):
                labels[str(row[0])] = str(row[1])
    finally:
        await conn.close()
    for _ in range(4):  # labels nest at most this deep (a tie's population's version's set)
        changed = False
        for raw, label in labels.items():
            for other, name in labels.items():
                if other != raw and other in label:
                    label = label.replace(other, name)
                    changed = True
            labels[raw] = label
        if not changed:
            break
    return labels


def _sorted(value: Json) -> Json:
    """Keys sorted at every level; list order kept (it is the API's order)."""
    if isinstance(value, dict):
        mapping = cast(dict[str, Json], value)
        return {k: _sorted(mapping[k]) for k in sorted(mapping)}
    if isinstance(value, list):
        return [_sorted(v) for v in cast(list[Json], value)]
    return value


async def _portal_token(http: httpx.AsyncClient, persona: str) -> str:
    """A portal session for a scenario client person, signed in on the firm's portal host with
    an emailed code (and, on first sign-in, a TOTP factor set up), as `make dev` would."""
    first, _, last = persona.partition("-")
    headers = {"host": PORTAL_HOST}
    start = await http.post(
        "/v1/portal/auth/start", json={"email": f"{first}.{last}@{PORTAL_SINK}"}, headers=headers
    )
    if start.status_code != 202:
        raise RuntimeError(f"{persona}: portal sign-in answered {start.status_code}")
    challenge = str(start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    if issued is None:
        raise RuntimeError(f"{persona}: no sign-in code issued")
    verified = await http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers=headers,
    )
    http.cookies.clear()
    body = cast(dict[str, Json], verified.json())
    if body.get("state") == "signed_in":
        return str(body["access_token"])
    token = body["mfa_token"]
    setup = await http.post(
        "/v1/portal/auth/mfa/setup", json={"mfa_token": token}, headers=headers
    )
    done = await http.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={
            "mfa_token": token,
            "totp": totp_at(str(setup.json()["manual_key"]), clock.system_now().timestamp()),
        },
        headers=headers,
    )
    http.cookies.clear()
    if done.status_code != 200:
        raise RuntimeError(f"{persona}: portal factor set-up answered {done.status_code}")
    return str(done.json()["session"]["access_token"])


async def capture(
    snapshot: str,
    *,
    app_url: str,
    identity_url: str,
    found: Mapping[str, str] | None = None,
) -> dict[str, Json]:
    """Every read's body, by name, from a database the scenario was loaded into at `snapshot`
    (with `load`); `found` is `server_ids`'s, for the paths that name one. The caller has
    configured nothing; this wires the engine, a fake identity
    provider and the portal domain and puts them back."""
    at = build(snapshot).snapshot.at
    reads = PROFILES[snapshot].reads
    by_label = {label: raw for raw, label in (found or {}).items()}
    previous_identity = os.environ.get(_IDENTITY_ENV)
    previous_portal = os.environ.get(_PORTAL_ENV)
    os.environ[_IDENTITY_ENV] = identity_url
    os.environ[_PORTAL_ENV] = PORTAL_BASE_DOMAIN
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
            # Sign-in challenges expire by the database's clock, so portal sessions are opened
            # before the snapshot clock is set; the reads themselves run under it.
            portal = {r.persona: await _portal_token(http, r.persona) for r in reads if r.portal}
            with clock.frozen(at):
                for read in reads:
                    path = read.path if isinstance(read.path, str) else read.path(done, by_label)
                    if read.portal:
                        token = portal[read.persona]
                        headers = {"Authorization": f"Bearer {token}", "host": PORTAL_HOST}
                    else:
                        token = idp.token(f"scenario-{read.persona}", mfa=True)
                        headers = {"Authorization": f"Bearer {token}"}
                    response = await http.get(path, params=dict(read.params), headers=headers)
                    if response.status_code != 200:
                        raise RuntimeError(f"{read.name}: {path} answered {response.status_code}")
                    http.cookies.clear()
                    done[read.name] = _sorted(response.json())
    finally:
        reset_verifier()
        await dispose_engine()
        for name, previous in ((_IDENTITY_ENV, previous_identity), (_PORTAL_ENV, previous_portal)):
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous
        settings.cache_clear()
        forget_flags()
    return done


def _standard_version_ids(standards: Json) -> dict[str, str]:
    """A standard and its versions are written through the service and the import endpoint
    (K-02-T18), whose ids are the server's own and differ on every load: each one's stable
    stand-in, from its key (and the version's number)."""
    out: dict[str, str] = {}
    body = cast(dict[str, object], standards)
    for item in cast(list[dict[str, object]], body.get("items", [])):
        out[str(item["id"])] = stable_id(f"standard:{item['key']}")
        for slot in ("current_version", "draft_version"):
            version = cast("dict[str, object] | None", item.get(slot))
            if version is not None:
                out[str(version["id"])] = stable_id(
                    f"standard-version:{item['key']}:{version['version']}"
                )
    return out


_UUID: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _replaced(value: object, ids: Mapping[str, str], inner: bool = False) -> object:
    """`ids` swapped in: whole strings, and with `inner` an id inside a string too (a citation
    key such as "led:<snapshot>:1010")."""
    if isinstance(value, str):
        if value in ids or not inner:
            return ids.get(value, value)
        return _UUID.sub(lambda m: ids.get(m.group(0), m.group(0)), value)
    if isinstance(value, list):
        return [_replaced(v, ids, inner) for v in cast(list[object], value)]
    if isinstance(value, dict):
        return {k: _replaced(v, ids, inner) for k, v in cast(dict[str, object], value).items()}
    return value


def _hashes(value: object, owner: str | None = None) -> object:
    """Each content hash (made from server ids, so new on every load) as a stand-in made from the
    stand-in id of the object that carries it."""
    if isinstance(value, list):
        return [_hashes(v, owner) for v in cast(list[object], value)]
    if not isinstance(value, dict):
        return value
    mapping = cast(dict[str, object], value)
    here = str(mapping["id"]) if isinstance(mapping.get("id"), str) else owner
    out: dict[str, object] = {}
    for k, v in mapping.items():
        if k in _HASH_KEYS and isinstance(v, str) and here is not None:
            out[k] = hashlib.sha256(f"{here}:{k}".encode()).hexdigest()
        else:
            out[k] = _hashes(v, here)
    return out


def stable(
    captured: Mapping[str, Json], found: Mapping[str, str] | None = None
) -> dict[str, Json]:
    """The captured bodies with every server-made standard and version id swapped for its stand-in,
    in every file, so links between fixtures hold and two exports are byte-identical; with
    `found` (`server_ids`), every other server id too, and the content hashes made from them."""
    ids = _standard_version_ids(captured["standards"]) if "standards" in captured else {}
    ids |= {raw: stable_id(label) for raw, label in (found or {}).items()}
    bodies = {name: _replaced(body, ids, bool(found)) for name, body in captured.items()}
    return {name: _hashes(body) for name, body in bodies.items()} if found else bodies


def document(snapshot: str, read: Read, body: Json) -> dict[str, Json]:
    """The file's content: where it came from, then the body."""
    return {
        "scenario": {
            "version": SCENARIO_VERSION,
            "hash": SCENARIO_HASH,
            "snapshot": snapshot,
            "slices": list(PROFILES[snapshot].slices),
        },
        "persona": read.persona,
        "request": read.label,
        "body": body,
    }


def _stem(snapshot: str) -> str:
    """The snapshot in a file name: lower case, no colon ("2026-09-24t1020")."""
    return snapshot.lower().replace(":", "")


def file_name(snapshot: str, read: Read) -> str:
    return f"{_stem(snapshot)}.{read.name}.json"


def exported_files(out: Path, snapshot: str) -> list[Path]:
    return sorted(out.glob(f"{_stem(snapshot)}.*.json"))


def render(
    snapshot: str, captured: Mapping[str, Json], found: Mapping[str, str] | None = None
) -> dict[str, str]:
    """File name -> text, deterministic (two-space indent, sorted keys, trailing newline)."""
    bodies = stable(captured, found)
    return {
        file_name(snapshot, read): json.dumps(
            document(snapshot, read, _sorted(bodies[read.name])), indent=2, ensure_ascii=False
        )
        + "\n"
        for read in PROFILES[snapshot].reads
    }


async def load(snapshot: str, superuser: str, app: str) -> None:
    """`make seed-demo` at `snapshot` with the export's slices into a throwaway database, and the
    export's flags on for the tenant (written as the loader's other bootstrap rows are)."""
    from abacus_tools.synthetic.scenarios.brightwater_hale import loader

    profile = PROFILES[snapshot]
    # The loader writes through the app's engine too: point it at the throwaway database first.
    # It writes the portal host (`brightwaterhale.<portal_base_domain>`) only where the domain
    # is set, so the load sees the export's.
    previous = os.environ.get(_PORTAL_ENV)
    os.environ[_PORTAL_ENV] = PORTAL_BASE_DOMAIN
    settings.cache_clear()
    await dispose_engine()
    configure_engine(app)
    try:
        await loader.load(superuser, snapshot, slices=profile.slices, wait=False)
    finally:
        await dispose_engine()
        if previous is None:
            os.environ.pop(_PORTAL_ENV, None)
        else:
            os.environ[_PORTAL_ENV] = previous
        settings.cache_clear()
    conn = await connect(superuser)
    try:
        await conn.execute(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "SELECT $1, f, 'true', 'fixture-export', 'F-04-T31' FROM unnest($2::text[]) f "
            "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = 'true'",
            TENANT,
            list(profile.flags),
        )
    finally:
        await conn.close()


async def _load_and_capture(
    snapshot: str, superuser: str, app: str, identity: str
) -> tuple[dict[str, Json], dict[str, str]]:
    await load(snapshot, superuser, app)
    found = await server_ids(snapshot, superuser)
    return await capture(snapshot, app_url=app, identity_url=identity, found=found), found


def export(snapshot: str, out: Path) -> list[Path]:
    """Load `snapshot` into a throwaway Postgres, read the MVP paths and write their files."""
    # Imported here: the throwaway Postgres is only for the command itself.
    from abacus_tools.quality.schema_check import provisioned_database

    with provisioned_database(roundtrip=False) as database:
        captured, found = asyncio.run(
            _load_and_capture(
                snapshot, database.superuser_dsn, database.app_url, database.identity_url
            )
        )
    out.mkdir(parents=True, exist_ok=True)
    for stale in exported_files(out, snapshot):
        stale.unlink()  # a read no longer exported leaves no file behind
    written: list[Path] = []
    for name, text in render(snapshot, captured, found).items():
        path = out / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def scenario_files() -> dict[str, str]:
    """Fixtures computed from the scenario's own data, with no database: N-02-T36's SIG-01 hub
    (`scenario.signatures-hub.json`), which the TypeScript scenarios are held to
    (`seed/signatures.export.test.ts`)."""
    from abacus_tools.synthetic.scenarios.brightwater_hale.signatures import hub_rows

    body = {"scenario": SCENARIO_VERSION, "slice": "signatures", "snapshot": "E0", **hub_rows()}
    return {"scenario.signatures-hub.json": json.dumps(body, indent=2, ensure_ascii=False) + "\n"}


def write_scenario_files(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, text in scenario_files().items():
        (out / name).write_text(text, encoding="utf-8")
        written.append(out / name)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.synthetic.fixture_export")
    parser.add_argument("--snapshot", choices=SNAPSHOTS, default="E0")
    parser.add_argument("--out", type=Path, default=EXPORTED)
    args = parser.parse_args(argv)
    for path in [*write_scenario_files(args.out), *export(args.snapshot, args.out)]:
        print(f"exported {path.relative_to(REPO) if path.is_relative_to(REPO) else path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
