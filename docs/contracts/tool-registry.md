# C17 · Agent tool registry

| Field | Value |
|---|---|
| Register row | C17 in `docs/contracts/README.md` |
| Version | v1 |
| Status | **frozen at v1** (P-10-T22, 2026-11-09, DEC-3001; stub P-10-T10, 2026-11-06). The slot, decorator, checks and the runtime are real; snapshot `backend/tests/contracts/c17_tools/v1.json`. No tool is registered yet: the first arrive with P-10-T28 |
| Provider epic | P-10 (SPEC-647; ADR-233) |
| Consumers | T-04 (tax tools), W-02, W-03, I-02, K-03, K-04, A-11, G-03 (read-only MCP) |
| Freeze sprint | S32 (Fri Jan 21, 2028) |
| Code | `backend/src/abacus/modules/agents/tools/registry.py`, `tools/runtime.py`; `abacus_tools/quality/tool_registry.py`; rule TOOL-001; migration 0750 (`agent_tool_calls`) |

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
| `approved_write` | one specific write | a valid approval grant whose action the approver holds now; the agent reaches the subject with the tool's declared `scope_action` (a `task_scope` action), never its own action (`agent: deny`) |

**Additive (P-10-T38, DEC-3402).** `ToolDecl.scope_action` (and `AgentTool.scope_action`): every
`approved_write` declares the `task_scope` action the runtime authorises the agent's reach to the
subject with at step 4 (`files.save_approved`: `file.propose`); `register_tool` refuses an
`approved_write` without one, one equal to its own action, or one holding a final verb, and any
other kind declaring one. The grant's consumer (step 6) re-checks the approver's own action. The
first `approved_write` and its siblings: `files.build_workbook` (compute, `file.propose`),
`files.propose_save` (propose, `file.propose`), `files.save_approved` (approved_write,
`file.save`).

## 4. Rules, and who enforces each
| Rule | Enforced by |
|---|---|
| A name or action holding a final verb (approve, sign off, release, send, post, export, transmit, decide, publish, adopt, resolve, accept, reject) can only be `approved_write` | TOOL-001, `register_tool`, `quality/tool_registry` |
| An `approved_write` action is `agent: deny`; any other tool's action is not | `quality/tool_registry` in `make check-fast` |
| An unregistered tool: a spec naming one fails codegen; a call answers `tool_not_registered` | `unregistered()` (P-10-T16), `tool()` |
| At most 200 rows, with IDs and code's totals (ADR-049, ADR-050) | `validate_tool` |
| The description is a registry prompt `tool.<name>@vN` | `validate_tool` |
| Questions, plans and final answers are output-schema fields, not tools | spec v2 (P-10-T16) |

## 5. Refusals and errors
Refusals: `consent_required`, `not_visible`, `out_of_scope`, `row_limit`, `stale_source`, `no_grant`.
Errors: `tool_not_registered`, `invalid_arguments`, `not_permitted`, `idempotency_key_reused`,
`tool_failed`. The model reads the code; nothing about a refused client is recorded or returned:
a refusal carries no id, count or name.

## 6. Calling a tool (runtime, P-10-T22)
`agents.api.call_tool(agent: AgentContext, call: ToolCallIn) -> ToolOutcome` is the only way a
handler runs. The harness (P-10-T25) calls it from its `call_tool` activity with the context
`identity` issued from the run row. `ToolCallIn` is `{run_id, step_seq, attempt, name, arguments,
grant_id?}`; `ToolOutcome` is `{name, ok, code?, result?, records_read, restricted, replayed,
active_ms}`, exactly one of `result` and `code` set. A refusal or error is an outcome, never an
exception.

| Order | Check | Answer when it fails |
|---|---|---|
| 1 | The tool is registered; `call.run_id` is the context's run | `tool_not_registered`; `not_permitted` |
| 2 | `arguments` validate against the input model; nothing runs otherwise (AC-G4: repair once, then escalate) | `invalid_arguments` |
| 3 | Every target is in the run's pinned `client_scope` (unpinned: the run engagement's client; a firm-level run reaches none) | `out_of_scope` (AC-R2) |
| 4 | `authorise(agent, action, target)`: `task_scope`, the initiator's live rights, walls, the matrix | a wall, relationship or tenancy layer: `not_visible` (404 semantics, AC-R3); a role: `not_permitted` |
| 5 | `data_class: tri`: C19's `require_tri_consent` for every taxpayer and year, **before any query**; it writes one `tri.tool_read` per taxpayer and covering consent | `consent_required` (AC-R4) |
| 6 | `approved_write`: `identity.consume_grant(grant, consumer, args_hash)`; the consumer is `uuid5(run:step:attempt)`, so only a retry of the same step passes | `no_grant` |
| 7 | `propose` and `approved_write`: claim `(run_id, step_seq, attempt)` in `agent_tool_calls`; a retry with the same arguments gets the stored answer (`replayed: true`) and the effect never runs twice | `idempotency_key_reused` (other arguments); `tool_failed` (the first still running) |
| 8 | The handler answers its output model | `tool_failed` (the claim is released) |
| 9 | Each row list is at most `max_rows` | `row_limit` (the tool paginates, AC-R6) |
| 10 | Unmasked TINs in any text value are replaced by their masks | — (no full TIN in a result, AC-R4) |
| 11 | `restricted` reads write identifier-only `agent_tool.restricted_read` access events before the result is handed over | — |

**Targets.** Code resolves them from the arguments, never from the model's claim about its own
scope: `engagement_id`/`engagement_ids`, `client_id`, and for TRI `client_entity_id`/
`client_entity_ids` with `tax_year`; with no engagement named, the run's own. An input model whose
records sit under another id implements `tool_targets(agent) -> ToolTargets`.

**Records read.** `ToolOutcome.records_read` is the sum of the row lists (1 for a single record).
The harness writes it to `agent_run_steps.records_read` with the step's state; a read writes no
audit event (SPEC-647 §4.5). Claims and their completion write `agent_tool.call_claimed`,
`.call_completed` and `.call_released` on the run.

**Next turn.** `agents.api.tool_result_for_model(outcome)` renders the result for the model: the
trusted fields as JSON, each `untrusted` field in its own `<untrusted name="…">` block, JSON-encoded
with `<` escaped (AC-R5, ADR-052). A refusal renders as its code alone.

## 7. Shapes `validate_tool` holds (P-10-T22)
- A read tool's row lists hold models with an `id`; `max_rows` is 1 to 200.
- A paginated tool takes `ToolPageIn {cursor?, limit ≤ 200}` and answers `ToolPageOut {next_cursor?, total}`; `total` is counted by code.
- `untrusted` names output fields.
- A `propose` or `approved_write` tool answers identifiers, numbers, dates, flags, enums, literals and text named as an id, code, key, state, status or kind; never free text or `untrusted` fields, since its answer is kept for the replay.

## 8. Freeze (v1)
The snapshot holds `ToolCallIn`, `ToolOutcome` (with every code), `ToolPageIn` and `ToolPageOut`
(`abacus_tools.contracts.IN_PROCESS["c17_tools"]`; `--check` covers it). Additions follow handshake
rule 5; a removed or retyped field, or a removed code, ships as v2 with one sprint of overlap.
The decorator's keywords and the four kinds are part of v1.

## 9. Change log
| Version | Date | Change |
|---|---|---|
| v1 | 2026-11-06 | Stub (P-10-T10, DEC-2409) |
| v1 | 2026-11-09 | Runtime and freeze (P-10-T22, DEC-3001): per-call authorisation, scope pinning, §7216 before the query, grants, the idempotency ledger (0750), row limits, TIN scrub, access events, `<untrusted>` rendering |
