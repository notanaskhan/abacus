"""C17's tool catalogue (P-10-T28; ADR-106 slot): every module's declared agent tools, registered
at `agents` import. A module that owns data declares its tools as `kernel.agent_tools.ToolDecl`
records in `<module>/agent_tools.py`, listed as its api's `AGENT_TOOLS`; nothing here reads a
table. `register_tool` validates each (names, kinds, never-verbs, 200 rows, ids, description
prompts) and refuses a duplicate.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from abacus.kernel.agent_tools import ToolDecl
from abacus.modules.agents.agent_tools import AGENT_TOOLS as AGENTS
from abacus.modules.agents.tools.registry import AgentTool, register_tool
from abacus.modules.engagements.api import AGENT_TOOLS as ENGAGEMENTS
from abacus.modules.evidence.api import AGENT_TOOLS as EVIDENCE
from abacus.modules.ledger.api import AGENT_TOOLS as LEDGER
from abacus.modules.requests.api import AGENT_TOOLS as REQUESTS

DECLARED: Final[tuple[ToolDecl, ...]] = (*ENGAGEMENTS, *REQUESTS, *EVIDENCE, *LEDGER, *AGENTS)


def as_tool(decl: ToolDecl) -> AgentTool:
    return AgentTool(
        name=decl.name,
        kind=decl.kind,
        action=decl.action,
        description=decl.description,
        data_class=decl.data_class,
        input_model=decl.input_model,
        output_model=decl.output_model,
        handler=decl.handler,
        untrusted=decl.untrusted,
        max_rows=decl.max_rows,
        paginate=decl.paginate,
        records_read=decl.records_read,
    )


def register_all(declared: Iterable[ToolDecl] = DECLARED) -> None:
    for decl in declared:
        register_tool(as_tool(decl))


register_all()
