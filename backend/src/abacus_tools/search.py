"""`python -m abacus_tools.search`: the firm search index's operator commands (P-02-T06; P-02
§4.5; DEC-4612). Owner tooling, synthetic and local data only unless an operator runs it against
an environment it is cleared for.

    reindex <tenant> [--type T] [--client C]   start or join a SearchReindexWorkflow (audited)
    index <tenant> <type> <id>                 rebuild one row now (inline)
    drift <tenant>                             run the drift check for one firm now
    purge <tenant>                             offboarding: delete every index row and recent

Query text never passes through this tool.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from uuid import UUID

from abacus.modules.platform.api import (
    purge_search_index,
    search_index_object,
    search_request_reindex,
)
from abacus.modules.platform.api import search_drift_firm as drift_firm


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.search")
    sub = parser.add_subparsers(dest="command", required=True)
    reindex = sub.add_parser("reindex")
    reindex.add_argument("tenant", type=UUID)
    reindex.add_argument("--type", dest="object_type")
    reindex.add_argument("--client", type=UUID)
    one = sub.add_parser("index")
    one.add_argument("tenant", type=UUID)
    one.add_argument("object_type")
    one.add_argument("object_id", type=UUID)
    drift = sub.add_parser("drift")
    drift.add_argument("tenant", type=UUID)
    purge = sub.add_parser("purge")
    purge.add_argument("tenant", type=UUID)
    args = parser.parse_args(argv)

    if args.command == "reindex":
        run_id = asyncio.run(
            search_request_reindex(
                args.tenant, args.object_type, client_id=args.client, actor="operator:cli"
            )
        )
        print(f"started {run_id}")
    elif args.command == "index":
        print(asyncio.run(search_index_object(args.tenant, args.object_type, args.object_id)))
    elif args.command == "drift":
        print(f"drifted {asyncio.run(drift_firm(args.tenant))}")
    else:
        print(f"purged {asyncio.run(purge_search_index(args.tenant))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
