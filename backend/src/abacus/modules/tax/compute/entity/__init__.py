"""The entity return engines (T-05; T-05 §4.4; DEC-77, ADR-050). PROTECTED (red files).

Pure functions over `Decimal`, golden-tested and CPA-reviewed: allocation by structure and
ownership period, §704(c) and §706(d) interim closings, capital and basis roll-forwards and the
tie-outs. Imports only `abacus.kernel.numeric`, `abacus.kernel.calendar` and the compute package's
own modules (the import-linter compute contract); independent of `tax.compute.individual`. Engines
land with T-05's compute rows (T-05-T08 onward); T-05-T04 reserves the package and its contracts.
"""
