# Capability specs v2 (P-10-T20)

One `<id>.yaml` per capability, compiled into `../_specs_v2.py` by
`python -m abacus_tools.codegen.agent_specs_v2` (part of `make regenerate`) and validated by
`abacus.modules.agents.spec_v2`. The v1 specs in `../*.yaml` are untouched.

The first v2 capability is `tax.return_drafter` v1 (T-04-T25, shape `workflow`: its own
`ReturnDrafterWorkflow` in `modules/tax/drafter_workflow.py`). `runtime.conformance` v1
(P-10-T40, shape `loop`; synthetic-only, never installable, `spec_v2.TEST_ONLY`) is the runtime's
reference over the T28 and T38 tools, run by `modules/agents/conformance.py`.
