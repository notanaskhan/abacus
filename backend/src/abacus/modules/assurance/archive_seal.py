"""The archive seal's manifest (A-07-T37; A-07 F8; ADR-159 proposed, P-43; ADR-004). PROTECTED
(red path). Pure: the lock workflow builds it from a snapshot, and the verify run rebuilds it from
the same rows, so a recomputation is byte-identical.

- **Leaves.** Every evidence version's SHA-256 (superseded versions kept), the deterministic row
  export of the binder's reviewable records (each row's content hash), and each packaged agent run
  record's `record_sha256` (P-09's trace manifests). Each leaf is `kind:id=sha256`; the Merkle root
  is SHA-256 over the sorted leaf hashes, an odd node carried up unchanged.
- **The audit chain.** The firm's newest sealed audit checkpoint (its `seq_to` and root) is in the
  manifest, so the seal binds the trail up to the lock.
- **Canonical form.** RFC 8785-style JSON: keys sorted, no whitespace, UTF-8, integers and strings
  only (no floats), so the manifest's SHA-256 is the seal (`7c41…a9e2` for Northwind).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, cast

CANONICALIZATION: Final = "rfc8785"
MANIFEST_VERSION: Final = 1


class EmptyBinder(ValueError):
    """Nothing to seal: an archive always holds at least the release's documents."""


@dataclass(frozen=True)
class Leaf:
    kind: str  # evidence_version · row · run_record
    id: str
    sha256: str

    def text(self) -> str:
        return f"{self.kind}:{self.id}={self.sha256}"


def merkle_root(leaves: Sequence[Leaf]) -> str:
    level = sorted(hashlib.sha256(leaf.text().encode()).hexdigest() for leaf in leaves)
    if not level:
        raise EmptyBinder
    while len(level) > 1:
        nxt = [
            hashlib.sha256((level[i] + level[i + 1]).encode()).hexdigest()
            for i in range(0, len(level) - 1, 2)
        ]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0]


def canonical(value: object) -> bytes:
    """RFC 8785 for the manifest's own types: sorted keys, no spaces, UTF-8, no floats."""

    def check(v: object) -> None:
        if isinstance(v, float):
            raise TypeError("the manifest holds no floats")
        if isinstance(v, dict):
            for k, x in cast("dict[object, object]", v).items():
                if not isinstance(k, str):
                    raise TypeError("manifest keys are strings")
                check(x)
        elif isinstance(v, list | tuple):
            for x in cast("list[object] | tuple[object, ...]", v):
                check(x)

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class Manifest:
    body: bytes
    sha256: str  # the seal
    merkle_root: str
    evidence_leaf_count: int
    row_leaf_count: int
    run_record_count: int


def build(
    *,
    tenant_id: str,
    engagement_id: str,
    work_item_id: str,
    archive_id: str,
    release_id: str,
    release_date: date,
    retention_until: date,
    compliance_retain_until: date,
    leaves: Sequence[Leaf],
    audit_checkpoint_seq_to: int | None,
    audit_checkpoint_root: str | None,
    checklist_sha256: str,
) -> Manifest:
    root = merkle_root(leaves)
    count = {
        k: sum(1 for leaf in leaves if leaf.kind == k)
        for k in ("evidence_version", "row", "run_record")
    }
    doc: dict[str, object] = {
        "manifest_version": MANIFEST_VERSION,
        "canonicalization": CANONICALIZATION,
        "tenant_id": tenant_id,
        "engagement_id": engagement_id,
        "work_item_id": work_item_id,
        "archive_id": archive_id,
        "release_id": release_id,
        "release_date": release_date.isoformat(),
        "retention_until": retention_until.isoformat(),
        "compliance_retain_until": compliance_retain_until.isoformat(),
        "checklist_sha256": checklist_sha256,
        "audit_checkpoint": {
            "seq_to": audit_checkpoint_seq_to if audit_checkpoint_seq_to is not None else 0,
            "root": audit_checkpoint_root or "",
        },
        "merkle_root": root,
        "leaves": [leaf.text() for leaf in sorted(leaves, key=lambda x: (x.kind, x.id))],
    }
    body = canonical(doc)
    return Manifest(
        body,
        hashlib.sha256(body).hexdigest(),
        root,
        count["evidence_version"],
        count["row"],
        count["run_record"],
    )
