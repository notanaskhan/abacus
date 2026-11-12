"""Firm search (P-02; ADR-241, P-33; contract C15 v1, `docs/contracts/c15-search.md`).

`spec` holds the registration contract every owning module uses (`SearchProjection`), `contract`
the HTTP models, `routes` the three routes behind `search.palette`. The routes answer 501 until
P-02-T08 lands the query and recents services; the index table arrives with P-02-T05 and the
indexer with P-02-T06.
"""
