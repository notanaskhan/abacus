# Route parity reports

`make route-parity ROUTE=direct|bedrock` writes `<route>-<date>.json` here and prints the SHA-256 to
record in `route_parity` (SPEC-010 Q2). A route serves `call()` while its record is under 90 days old
and the report `passed` (structured reply, prompt caching, batch access per catalog model).

From P-10-T13 (ADR-234 §7) each model is also probed for **tools** (one offered tool with
`tool_choice: any`, schema-valid arguments, then a `tool_result` turn that ends the conversation) and
**documents** (a one-page synthetic PDF read back). A report whose models all pass both sets
`tool_parity: true`; record that on the route's `route_parity` entry. A loop-shaped spec is refused on
a route without it (`routes.route_enabled_for(route, "loop")`).

| Route | Latest report | `passed` | `tool_parity` |
|---|---|---|---|
| direct | `direct-2026-10-11.json` | yes | no (predates P-10-T13) |
| bedrock | none committed | — | — |

Open: a Bedrock and a direct run with the P-10-T13 probes, in the evaluation account, before a loop
spec goes live (P-10-T46 runs the conformance evals on both routes).
