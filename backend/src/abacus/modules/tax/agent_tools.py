"""The tax tools, where C17's registry gate and the spec codegen look for them (T-04-T25).

`abacus_tools.quality.tool_registry.import_agent_tools` imports every module's `agent_tools.py`;
T-04-T19's tools are declared in `tools.py`, so this imports it (registration happens at import).
"""

from __future__ import annotations

from abacus.modules.tax import tools  # registers the tax.* tools at import

# T-06-T38 (DEC-5831): `ledger.tb_mapper` mode `tax_lines`'s propose tool (tax.suggest_tax_lines).
from abacus.modules.tax import tb_mapper_tools as tb_mapper_tools  # noqa: E402

__all__ = ["tools"]
# T-07-T14: the instrument reader's tools (tax.read_instrument_clauses, tax.read_trust_facts,
# tax.propose_trust_determinations) register at their module's import.
from abacus.modules.tax import instrument_tools as instrument_tools
