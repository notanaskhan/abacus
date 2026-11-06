# C17 · Agent tool registry

| Field | Value |
|---|---|
| Register row | C17 in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub (P-10-T10, 2026-11-06). The slot, decorator and checks are real; no tool is registered and the harness lands with P-10-T17, T21 |
| Provider epic | P-10 (SPEC-647; ADR-233) |
| Consumers | T-04 (tax tools), W-02, W-03, I-02, K-03, K-04, A-11, G-03 (read-only MCP) |
| Freeze sprint | S32 (Fri Jan 21, 2028) |
| Code | `backend/src/abacus/modules/agents/tools/registry.py`; `abacus_tools/quality/tool_registry.py`; rule TOOL-001 |

## 1. Purpose
Agents read and propose through narrow, typed tools, each in the module that owns the data. There is
no generic query tool.

## 2. Declaring a tool
```python
# modules/tax/agent_tools.py
from abacus.modules.agents.api import agent_tool

@agent_tool(
    name="tax.read_return",       # <module>.<verb_noun>; description is tool.tax.read_return@v1
    kind="read",                  # read | compute | propose | approved_write
    action="return.read",         # matrix action, authorised against AgentContext (ADR-025)
    data_class="tri",             # §7216 consent is checked before the read
    input_model=ReadReturnIn,
    output_model=ReadReturnOut,
    untrusted=("preparer_notes",),  # wrapped <untrusted> in the next model turn
    paginate=True,
    records_read="tax_return",    # counted into the run's Records read
)
async def read_return(agent: AgentContext, args: ReadReturnIn) -> ReadReturnOut: ...
```

## 3. Kinds and authority
| Kind | Side effects | Authorised by |
|---|---|---|
| `read` | none | `task_scope` ∩ initiator's live rights ∩ walls and `visible()` ∩ §7216 |
| `compute` | none: deterministic code over reads | as `read` |
| `propose` | inserts a suggestion, proposal, draft, issue, to-do proposal or question only | actions the matrix gives agents as `task_scope` |
| `approved_write` | one specific write | a valid approval grant whose action the approver holds now |

## 4. Rules, and who enforces each
| Rule | Enforced by |
|---|---|
| A name or action holding a final verb (approve, sign off, release, send, post, export, transmit, decide, publish, adopt, resolve, accept, reject) can only be `approved_write` | TOOL-001, `register_tool`, `quality/tool_registry` |
| An `approved_write` action is `agent: deny`; any other tool's action is not | `quality/tool_registry` in `make check-fast` |
| An unregistered tool: a spec naming one fails codegen; a call answers `tool_not_registered` | `unregistered()` (P-10-T16), `tool()` |
| At most 200 rows, with IDs and code's totals (ADR-049, ADR-050) | `validate_tool` |
| The description is a registry prompt `tool.<name>@vN` | `validate_tool` |
| Questions, plans and final answers are output-schema fields, not tools | spec v2 (P-10-T16) |

## 5. Refusals
`consent_required`, `not_visible`, `out_of_scope`, `row_limit`, `stale_source`, `no_grant`. The model
reads the code; nothing about a refused client is recorded or returned.

## 6. Change log
| Version | Date | Change |
|---|---|---|
| v1 | 2026-11-06 | Stub (P-10-T10, DEC-2409) |
