"""`python -m abacus_tools.evals.publish SUMMARY.json --database-url URL [--environment ENV]`:
load a run's summary into an evaluation store (TASK-020 D3). DEPLOY PIPELINE ONLY: the deploy
pipeline (TASK-014) publishes CI's runs into its environment, so the gateway's eligibility check
(`eval_eligible`) sees them. Never run by hand against a deployed environment.

A summary is never trusted as it stands:
- it is validated as a frozen model;
- its model must be its tier's (`MODELS`), and its prompt and suite the agent's current ones;
- its status and reasons are recomputed from its case rows against the current suite, and a
  summary claiming anything else is refused (a forged pass);
- a real-model summary must carry CI's signature (`ABACUS_EVAL_SIGNING_KEY`, HMAC-SHA256);
- a summary no newer than the store's latest finished run for the same key is refused (a
  replay);
- a database away from this machine is refused unless `--environment staging|production` is
  named and the summary's signature verifies.

It connects as the store's owner (`abacus_tools.stack.connect_db`, the tooling's one direct
connection), because the app role has no privileges on the store.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import cast

from abacus.ai_gateway import model_id
from abacus.modules.agents.api import spec
from abacus_tools.evals.metrics import Attempt
from abacus_tools.evals.runner import baseline, store_finish, store_start, suite_for
from abacus_tools.evals.summary import Summary, verified
from abacus_tools.evals.verdict import judge
from abacus_tools.stack import connect_db, is_loopback

REMOTE_ENVIRONMENTS = ("staging", "production")


class Refused(ValueError):
    """The summary can't be published (the message says why; nothing was written)."""


def check(summary: Summary, *, database_url: str, environment: str | None) -> None:
    """Every check that needs no database (raises `Refused`)."""
    agent = spec(summary.agent)
    if summary.route not in ("fake", "direct", "bedrock"):
        raise Refused("the route isn't a model route")
    if summary.model != model_id(summary.tier, summary.route):
        raise Refused("the model isn't its tier's on its route")
    if summary.prompt_version != agent.prompt:
        raise Refused("the prompt isn't the agent's current one")
    suite = suite_for(summary.agent)
    if summary.suite_version != suite.version:
        raise Refused("the suite isn't the current one")
    signed = verified(summary)
    if not summary.fake and not signed:
        raise Refused("a real-model run must carry CI's signature")
    if not is_loopback(database_url) and not (environment in REMOTE_ENVIRONMENTS and signed):
        raise Refused("a remote store needs --environment staging|production and a signed run")
    if summary.status in ("aborted_cost", "errored"):
        return  # these only ever revoke eligibility
    cases = {c.id: c for c in suite.cases}
    attempts: list[Attempt] = []
    for row in summary.cases:
        case = cases.get(row.case_id)
        if case is None:
            raise Refused(f"case {row.case_id!r} isn't in the suite")
        attempts.append((case, row.observation()))
    routing = agent.confidence_routing
    verdict = judge(
        suite,
        attempts,
        fake=summary.fake,
        aborted=False,
        baseline=baseline(summary.agent, summary.tier),
        current_below=float(routing.below),
        route=routing.route,
    )
    if verdict.status != summary.status or sorted(verdict.reasons) != sorted(summary.reasons):
        raise Refused("the status doesn't follow from the case rows")


async def publish(summary: Summary, database_url: str, environment: str | None = None) -> None:
    check(summary, database_url=database_url, environment=environment)
    conn = await connect_db(database_url)
    try:
        async with conn.transaction():
            newest = await conn.fetchval(
                "SELECT max(finished_at) FROM eval_runs WHERE agent_id = $1 AND tier = $2 "
                "AND model = $3 AND prompt_version = $4 AND suite_version = $5 AND subset = $6 "
                "AND tenant_id IS NULL AND status <> 'running'",
                summary.agent,
                summary.tier,
                summary.model,
                summary.prompt_version,
                summary.suite_version,
                summary.subset,
            )
            if newest is not None and summary.finished_at <= newest:
                raise Refused("a newer run is already published for this key (a replay)")
            await store_start(conn, summary)
            await store_finish(conn, summary)
    finally:
        await conn.close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.evals.publish")
    parser.add_argument("summary", type=Path)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--environment", choices=REMOTE_ENVIRONMENTS, default=None)
    args = parser.parse_args(argv)
    summary = Summary.model_validate_json(cast(Path, args.summary).read_text())
    try:
        asyncio.run(
            publish(summary, cast(str, args.database_url), cast(str | None, args.environment))
        )
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
