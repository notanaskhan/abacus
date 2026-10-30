# M10 · Client-facing gate (Tue Jul 13, 2027)

Chapter 01 §1.2.2's M10: PW2 opens; the first firm goes client-facing. This file holds results only:
never client data, firm names or contract terms. Sections are owned by the tasks that prove them; a
row that is not green on the day moves the gate or comes out by name.

## Signatures (N-02-T17)

| # | Row | Evidence | State |
|---|---|---|---|
| M10-SIG-1 | Letters at least in record mode: every engagement entering PW2 has its signed engagement letter imported (SIG-01 Completed, evidence opens) | per firm: imported letters versus engagements in scope, from the dossier's Content section (`docs/ops/pilot/import-signed-letters.md` §Order) | not yet: no PW2 firm |
| M10-SIG-2 | `signatures.envelopes` on for the firm in production, with the other founder approving (`make flag`) | the flag event's id | not yet |
| M10-SIG-3 | Record mode walked on the production canary (M8's deliverable) | the walk's date and the canary envelope's id | not yet: the production stack and canary are not provisioned |
| M10-SIG-4 | RB-18 read by both founders (the outage path for record mode and wet signatures) | the runbook's review row | first notes written (N-02-T17) |
