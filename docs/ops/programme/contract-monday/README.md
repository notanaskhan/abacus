# Contract Monday notes (F-09 A4; one per sprint)

On the first day of each sprint AY runs

    python -m abacus_tools.contract_monday --sprint S<n> --on <date> \
        --out docs/ops/programme/contract-monday/<date>-S<n>.md

after refreshing `docs/ops/vendors/README.md` (every open row's status and date), then answers each
trigger's "Fired?" and, for a fired one, takes the register's contingency that day and writes what
was done. The note is committed that day. It never holds a price, a contract term, a partner's name
or counsel's advice: those stay in the vault, and the tracker holds only status, dates and vault
references.

| Sprint | Date | Note | Fired triggers | Notes |
|---|---|---|---|---|
| S15 | 2027-05-17 | — | — | not written: on 2026-10-30 every one of the tracker's 30 rows still reads `to file`, so a note would list them all past due. The tracker needs AY's real statuses first (vault) |
