"""The tax tools, where C17's registry gate and the spec codegen look for them (T-04-T25).

`abacus_tools.quality.tool_registry.import_agent_tools` imports every module's `agent_tools.py`;
T-04-T19's tools are declared in `tools.py`, so this imports it (registration happens at import).
"""

from __future__ import annotations

from abacus.modules.tax import tools as _tools  # noqa: F401 -- registers the tax.* tools

__all__: list[str] = []
