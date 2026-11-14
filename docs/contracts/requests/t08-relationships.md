# Contract request: the relationships graph read model (T14 → T-08)

F-07-T21 (TASK-7950). From F-07's T14 GraphCanvas and TPL-14 (Ridgeline relationships) to T-08.
Today the graph reads `ClientRelationshipOut`; the graph's own read model must serve nodes and
edges with the facts below.

## Screen states
TPL-14 a (default graph, Jonah Feld selected, two K-1s at risk), b (list view), c (trust
variant), d (external node), e (single entity), f (after Ridgeline's approval, K-1s released).

## Fields
Node: `id`, `kind` (`person` · `partnership` · `entity` · `trust` · `return` · `external`),
`label`, `client_id` (null for an external node), `masked` (a walled node's label withheld).
Edge: `from`, `to`, `kind` (`owns` · `partner_of` · `k1_to` · `beneficiary_of`), `percent`,
`since`, `until`, `source` (`ownership_period` · `k1_package` · `manual`), `state`
(`at_risk` · `released`). Saved positions per viewer.

## Seed figures
Ridgeline year-end ownership 2 + 38 + 30 + 5 + 25 = 100 %; Pell Street Ventures 35 % through
6/30/2025; K-1s to the Feld and Shah 1040s.
