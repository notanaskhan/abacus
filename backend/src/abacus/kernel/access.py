"""Access events (Q-02-T20): `record_reads`, `register_access_kind` and the
reader `run_reads`. The writer lives in
`kernel.uow.access`, the only package that owns a tenant connection's transaction (UOW-002)."""

from abacus.kernel.uow.access import (
    FLAGS,
    AccessSubject,
    RunRead,
    UnknownAccessKind,
    ensure_partitions,
    record_reads,
    register_access_kind,
    run_reads,
)

__all__ = [
    "FLAGS",
    "AccessSubject",
    "RunRead",
    "UnknownAccessKind",
    "ensure_partitions",
    "record_reads",
    "register_access_kind",
    "run_reads",
]
