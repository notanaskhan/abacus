"""Access events (Q-02-T20): `record_reads` and `register_access_kind`. The writer lives in
`kernel.uow.access`, the only package that owns a tenant connection's transaction (UOW-002)."""

from abacus.kernel.uow.access import (
    FLAGS,
    AccessSubject,
    UnknownAccessKind,
    ensure_partitions,
    record_reads,
    register_access_kind,
)

__all__ = [
    "FLAGS",
    "AccessSubject",
    "UnknownAccessKind",
    "ensure_partitions",
    "record_reads",
    "register_access_kind",
]
