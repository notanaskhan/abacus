"""P-09-T03 (TASK-6210; SPEC-648 AC-6; ADR-230; DEC-2810): the AgentBlocks v1 JSON Schema export.

TASK-5004 built the server schema and validators; this row's last clause is the JSON Schema in
`packages/api-client`. The schema is the model's own (no drift), names exactly the nine v1 parts,
and stays closed (no extra properties), so a client refuses what the server refuses by shape.
"""

from __future__ import annotations

import json

from abacus.modules.agents.blocks import AgentBlocks
from abacus_tools.codegen import agent_blocks_schema

V1_PARTS = {
    "ParagraphPart", "TablePart", "KvPart", "MetricPart", "FilePart", "BadgePart",
    "CiteListPart", "OptionsPart", "EntityRefPart",
}  # fmt: skip


def test_the_committed_schema_is_the_models() -> None:
    assert agent_blocks_schema.main(["--check"]) == 0


def test_it_names_exactly_the_nine_v1_parts_and_is_closed() -> None:
    schema = json.loads(agent_blocks_schema.render())
    parts = {k for k in schema["$defs"] if k.endswith("Part")}
    assert parts == V1_PARTS
    assert all(schema["$defs"][p].get("additionalProperties") is False for p in parts)
    assert schema["additionalProperties"] is False
    assert schema["title"] == "AgentBlocks v1"


def test_the_version_is_pinned() -> None:
    assert AgentBlocks.model_fields["version"].default == 1
