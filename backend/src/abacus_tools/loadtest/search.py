"""C15 search at 1M documents (P-02-T13; P-02 §10 item 6; ADR-241; DEC-4726; RB-82).

Run, against a local stack only:

    python -m abacus_tools.loadtest.search seed --tenant <uuid> [--documents 1000000]
    python -m abacus_tools.loadtest.run --profile search_december
    python -m abacus_tools.loadtest.search check --tenant <uuid> --report <run.json>
        [--since <iso>]
    python -m abacus_tools.loadtest.search clean --tenant <uuid>

`seed` grows a synthetic tenant's index to `--documents` rows (Brightwater Hale after the scenario
load and a reindex): every synthetic row copies the scope columns of one of the tenant's real
documents (object type, group, scope kind, engagement, work item, client, owner, data class,
target), so `visible()`, walls and RLS cost what they cost in production; only the title gains a
deterministic suffix and the identifiers a `loadtest:<n>` marker that `clean` deletes by. Rows are
written in batches of `--batch` through the unit of work as the indexer's own system context, one
`search_index.loadtest_seeded` audit event per batch. It refuses a firm that is not synthetic.

`check` applies P-02's exit numbers: the `search_first` group (the first group served, Clients) at
p95 ≤ 250 ms from the run's JSON report, and the relay lag p95 ≤ 5 s over the documents the relay
(re)indexed during the run (`indexed_at` and `source_updated_at` both after `--since`; seeded rows
are dated a year back and never count). The live alarm on the same lag is `SearchIndexLagMs` p95
(`infra/modules/search`, from the indexer's `search.index_lag` line).

Local only: `db_guard` refuses a hosted database and a held deploy lock, as `run.py` does. Exit
codes: 0 passed, 1 a target missed, 2 refused or misconfigured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import CursorResult, text

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import is_synthetic_firm
from abacus_tools.local import db_guard

FIRST_GROUP_P95_MS: Final = 250.0
LAG_P95_SECONDS: Final = 5.0
DEFAULT_DOCUMENTS: Final = 1_000_000
DEFAULT_BATCH: Final = 50_000
ACTOR: Final = "system:search_loadtest"
MARKER: Final = "loadtest:"  # the SQL below spells it out (no string-built SQL)
_LOCAL: Final = frozenset({"local", "test"})

# 64 syllables: a row's suffix is two of them and a number, so titles spread over the trigram
# space instead of repeating one word a million times.
_SYLLABLES: Final = [
    "ba",
    "be",
    "bi",
    "bo",
    "bu",
    "da",
    "de",
    "di",
    "do",
    "du",
    "fa",
    "fe",
    "fi",
    "fo",
    "fu",
    "ga",
    "ge",
    "gi",
    "go",
    "gu",
    "ka",
    "ke",
    "ki",
    "ko",
    "ku",
    "la",
    "le",
    "li",
    "lo",
    "lu",
    "ma",
    "me",
    "mi",
    "mo",
    "mu",
    "na",
    "ne",
    "ni",
    "no",
    "nu",
    "pa",
    "pe",
    "pi",
    "po",
    "pu",
    "ra",
    "re",
    "ri",
    "ro",
    "ru",
    "sa",
    "se",
    "si",
    "so",
    "su",
    "ta",
    "te",
    "ti",
    "to",
    "tu",
    "va",
    "ve",
    "vi",
    "vo",
]

_TEMPLATES: Final = text(
    "SELECT count(*) FROM search_documents WHERE identifiers_text NOT LIKE 'loadtest:%'"
)
_COUNT: Final = text("SELECT count(*) FROM search_documents")
_SEED: Final = text(
    """
    WITH tpl AS (
        SELECT row_number() OVER (ORDER BY object_type, object_id) - 1 AS rn, *
        FROM search_documents WHERE identifiers_text NOT LIKE 'loadtest:%'
    ), words AS (SELECT CAST(:words AS text[]) AS w)
    INSERT INTO search_documents (
        tenant_id, object_type, object_id, group_key, scope_kind, engagement_id, work_item_id,
        client_id, owner_user_id, data_class, title, context, identifiers_text, related,
        related_text, status_code, status_context, due_on, tag, use_count, target_params, tsv,
        source_updated_at
    )
    SELECT
        tpl.tenant_id, tpl.object_type, gen_random_uuid(), tpl.group_key, tpl.scope_kind,
        tpl.engagement_id, tpl.work_item_id, tpl.client_id, tpl.owner_user_id, tpl.data_class,
        left(tpl.title || ' ' || s.suffix, 300), tpl.context, 'loadtest:' || n, tpl.related,
        tpl.related_text, tpl.status_code, tpl.status_context, tpl.due_on, tpl.tag,
        tpl.use_count, tpl.target_params,
        setweight(to_tsvector('simple', left(tpl.title || ' ' || s.suffix, 300)), 'A')
          || setweight(to_tsvector('simple', 'loadtest:' || n), 'B')
          || setweight(to_tsvector('simple', tpl.related_text), 'C'),
        clock_timestamp() - interval '400 days'
    FROM generate_series(CAST(:lo AS bigint), CAST(:hi AS bigint)) AS n
    CROSS JOIN words
    CROSS JOIN LATERAL (
        SELECT words.w[1 + n % 64] || words.w[1 + (n / 64) % 64] || ' ' || (n % 10000) AS suffix
    ) AS s
    JOIN tpl ON tpl.rn = n % :templates
    """
)
_CLEAN: Final = text("DELETE FROM search_documents WHERE identifiers_text LIKE 'loadtest:%'")
_LAG: Final = text(
    "SELECT count(*) AS n, percentile_cont(0.95) WITHIN GROUP (ORDER BY "
    "extract(epoch FROM indexed_at - source_updated_at)) AS p95 FROM search_documents "
    "WHERE indexed_at >= :since AND source_updated_at >= :since"
)


class Refused(Exception):
    """The tool will not run here."""


def _refuse_hosted() -> None:
    if settings().environment not in _LOCAL:
        raise Refused(f"environment {settings().environment!r} is not local or test")
    problems = db_guard.violations()
    if problems:
        raise Refused("; ".join(problems))
    holder = db_guard.lock_holder()
    if holder is not None:
        raise Refused(f"the deploy lock is held by {holder}")


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", ACTOR)


async def seed(tenant_id: UUID, documents: int, batch: int) -> int:
    """Grow the tenant's index to `documents` rows; answers the rows added."""
    if not await is_synthetic_firm(_system(tenant_id)):
        raise Refused("the firm is not synthetic")
    async with tenant_session(_system(tenant_id)) as session:
        templates = int(await session.scalar(_TEMPLATES) or 0)
        present = int(await session.scalar(_COUNT) or 0)
    if templates == 0:
        raise Refused("the tenant has no indexed documents to copy: load and reindex it first")
    added = 0
    lo = present
    while lo < documents:
        hi = min(documents, lo + batch) - 1
        async with uow(_system(tenant_id)) as tx:
            await tx.session.execute(
                _SEED, {"lo": lo, "hi": hi, "templates": templates, "words": list(_SYLLABLES)}
            )
            tx.record(
                "search_index.loadtest_seeded",
                target=Target("search_index", tenant_id),
                after=Ref(rows=hi - lo + 1),
            )
        added += hi - lo + 1
        lo = hi + 1
    return added


async def clean(tenant_id: UUID) -> int:
    async with uow(_system(tenant_id)) as tx:
        gone = cast(CursorResult[Any], await tx.session.execute(_CLEAN))
        tx.record(
            "search_index.loadtest_seeded",
            target=Target("search_index", tenant_id),
            after=Ref(rows=-(gone.rowcount or 0)),
        )
    return gone.rowcount or 0


@dataclass(frozen=True)
class Verdict:
    first_group_p95_ms: float | None
    lag_samples: int
    lag_p95_seconds: float | None
    documents: int
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def first_group_p95(report: dict[str, object], group: str = "search_first") -> float | None:
    """The group's p95 from a `run.py` JSON report (`groups: [{name, p95_ms, …}]`)."""
    for g in cast(list[dict[str, object]], report.get("groups", [])):
        if g.get("name") == group and isinstance(g.get("p95_ms"), int | float):
            return float(cast(float, g["p95_ms"]))
    return None


def judge(
    p95_ms: float | None, lag_n: int, lag_p95: float | None, documents: int, wanted: int
) -> Verdict:
    failures: list[str] = []
    if documents < wanted:
        failures.append(f"index holds {documents} documents, under {wanted}")
    if p95_ms is None:
        failures.append("the report has no search_first group")
    elif p95_ms > FIRST_GROUP_P95_MS:
        failures.append(f"first-group p95 {p95_ms:.0f} ms is over {FIRST_GROUP_P95_MS:.0f} ms")
    if lag_n == 0 or lag_p95 is None:
        failures.append("no document was reindexed by the relay during the run")
    elif lag_p95 > LAG_P95_SECONDS:
        failures.append(f"relay lag p95 {lag_p95:.2f} s is over {LAG_P95_SECONDS:.0f} s")
    return Verdict(p95_ms, lag_n, lag_p95, documents, tuple(failures))


async def check(tenant_id: UUID, report: Path, since: datetime | None, wanted: int) -> Verdict:
    """P-02's targets over the run's report and the index (`since` defaults to the run's start)."""
    loaded = cast(dict[str, object], json.loads(report.read_text(encoding="utf-8")))
    if since is None:
        since = datetime.fromisoformat(str(loaded["started_at"]))
    async with tenant_session(_system(tenant_id)) as session:
        documents = int(await session.scalar(_COUNT) or 0)
        lag = (await session.execute(_LAG, {"since": since})).one()
    p95 = None if lag.p95 is None else float(lag.p95)
    return judge(first_group_p95(loaded), int(lag.n), p95, documents, wanted)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.loadtest.search")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("seed", "check", "clean"):
        p = sub.add_parser(name)
        p.add_argument("--tenant", type=UUID, required=True)
        if name in ("seed", "check"):
            p.add_argument("--documents", type=int, default=DEFAULT_DOCUMENTS)
        if name == "seed":
            p.add_argument("--batch", type=int, default=DEFAULT_BATCH)
        if name == "check":
            p.add_argument("--report", type=Path, required=True)
            p.add_argument("--since", type=datetime.fromisoformat, default=None)
    args = parser.parse_args(argv)
    try:
        _refuse_hosted()
        if args.command == "seed":
            added = asyncio.run(seed(args.tenant, args.documents, args.batch))
            print(f"seeded {added} documents")
            return 0
        if args.command == "clean":
            print(f"deleted {asyncio.run(clean(args.tenant))} documents")
            return 0
        verdict = asyncio.run(check(args.tenant, args.report, args.since, args.documents))
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    print(json.dumps(verdict.__dict__ | {"passed": verdict.passed}, default=str, indent=2))
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main())
