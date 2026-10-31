# A-02 hand-off notes (A-02-T39)

A-02 (trial balance, ledger connector, integration framework) is built: C9 v1 (the TB-layers half) and C20 v1 are frozen; the QuickBooks Online read is the live ledger (dark until a firm's `connections.live_ledger` is on). Each note says what a consumer epic receives, the seam it plugs into, and what A-02 deliberately left to it. Link the note from the consumer epic's issue.

| Epic | Note | Seam |
|---|---|---|
| A-03 | [A-03.md](A-03.md) | C9 taxonomy on the TB of record |
| A-05 | [A-05.md](A-05.md) | document-extracted TB versions (AUD-06b) |
| A-06 | [A-06.md](A-06.md) | `ledger.register_adjustment_source` (AUD-06d) |
| A-09 | [A-09.md](A-09.md) | one ledger for many entities (OneWorld), the entity strip |
| C-01 | [C-01.md](C-01.md) | hourly sync on the same connector |
| T-01 | [T-01.md](T-01.md) | `integrations` package for the CCH file bridge |
| T-06 | [T-06.md](T-06.md) | TB hand-off to tax (AUD-38, C12) |
| W-01 | [W-01.md](W-01.md) | catalogue v2 on the C20 framework |

Design deviations: DF-19 (read-only connect copy) is recorded in `docs/screens/POR-16.md` (the copy table and parity notes). Runbooks: RB-04 (provider outage), RB-05 (expiring-connections wave).
