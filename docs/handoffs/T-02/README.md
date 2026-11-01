# T-02 hand-off notes and task log (T-02-T35)

T-02 (returns workflow, organizers and K-1s) is built: 35 rows, T-02-T15 folded into T-01-T18.
Owner of every row in the solo edition: the builder (ayushkbhatia); notanaskhan rows were built in
the same sessions. Contracts: `tax-returns.md` and `k1-packages.md` frozen v1, `questionnaires.md`
live (DEC-1674). Runbooks RB-44 and RB-45.

| Epic | Receives | Seam | Left to it | Acknowledged |
|---|---|---|---|---|
| T-03 | the flags' retirement into the `tax` entitlement and `requests` (T-03-T19, Nov 16, 2027) | the feature-flag registry | renew or retire the four flags; adopt the paths | — |
| T-04 | agent blocks on TAX-02/03 drawn only where planned screens are visible | `tax_agents.enabled` (T-04-T09) | every tax agent; consent condition 6 already gates TRI | — |
| R-02 | K-1 packages and their access events (the C10 precursor) | C10 deliverables | the K-1 deliverable kind and retention | — |
| A-04, A-08 | questionnaires and inquiries (`questionnaires.v1`) | `questionnaires.md` (live, unfrozen) | their inquiry kinds | — |
| I-01 | return status and the draft-K-1 blocker as gate facts | C13 registration | Home rows | — |

## Open at close
- No route revokes one package's `k1_recipient` grant (RB-45 contains through the flag).
- Hosted journey runs (staging, canary) are `test.fixme` until the live swaps reach staging
  (T-02-T32); the parity locks run on PRs labelled `parity` and nightly (T-02-T33).
