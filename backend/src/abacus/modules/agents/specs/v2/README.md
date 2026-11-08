# Capability specs v2 (P-10-T20)

One `<id>.yaml` per capability, compiled into `../_specs_v2.py` by
`python -m abacus_tools.codegen.agent_specs_v2` (part of `make regenerate`) and validated by
`abacus.modules.agents.spec_v2`. The v1 specs in `../*.yaml` are untouched.

The first v2 capability, `runtime.conformance` v1 (synthetic-only, never installable), lands with
P-10-T40 once its tools (T28, T38) are registered; until then this folder holds no spec and
`SPECS_V2` is empty.
