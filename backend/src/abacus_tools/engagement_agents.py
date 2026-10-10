"""Start the engagement agent for a firm's open engagements (SPEC-027 Q7; TASK-051).

Run: python -m abacus_tools.engagement_agents start <tenant-id>

Idempotent: an engagement whose agent is running just records it. Only firms with
`engagement_agent.enabled` on; the daily tick then runs without waiting for an event.
"""

from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from abacus.modules.agents.api import start_agents


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "start":
        print("usage: python -m abacus_tools.engagement_agents start <tenant-id>")
        return 2
    count = asyncio.run(start_agents(UUID(argv[1])))
    print(f"signalled {count} engagement agent(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
