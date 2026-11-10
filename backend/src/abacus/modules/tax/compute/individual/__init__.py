"""The individual return workspace's compute package (T-04-T11; T-04 §4.4; ADR-050, ADR-231;
DEC-3124).

Pure functions over frozen typed inputs, `Decimal` at precision 28 with explicit quantisation,
each answering its figures with a `Stamp` (`engine_name`, `engine_version`, `inputs_hash`). They
compute the review workspace's arithmetic only: line rollups, ties, allocations and limits. Tax,
credits and filed forms are the engine of record's (ADR-231); NY and NYC tax lines enter as
imports (DEC-77). Imports: `abacus.kernel.numeric` and the parameters file only.
"""
