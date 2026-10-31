"""Screened file storage for modules that may not import evidence (K-01-T18; DEC-1759).

Evidence registers its upload screen (scan, type sniff, store) and its staged reader here.
Methodology may import only identity and platform (ADR-008, BOUND-002), and evidence's own service
reaches methodology through engagements, so a direct import would also close a loop through
evidence's routes (ADR-012). Methodology stores and reads its source files through these two
functions instead; nothing is stored when the screen refuses a file.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StoredFile:
    """A file that passed the screen: its cleaned name, sniffed type, digest and storage key."""

    file_name: str
    media_type: str
    sha256: str
    key: str
    version_id: str


Screen = Callable[[UUID, bytes, str], Awaitable[StoredFile]]
Read = Callable[[UUID, str, str, str, int], Awaitable[bytes]]
_store: list[tuple[Screen, Read]] = []


def register_file_store(screen: Screen, read: Read) -> None:
    """Evidence registers once, at import (`evidence.api`)."""
    if _store and _store[0] != (screen, read):
        raise RuntimeError("the file store is already registered")
    _store[:] = [(screen, read)]


def _registered() -> tuple[Screen, Read]:
    if not _store:
        raise RuntimeError("no file store is registered (evidence.api registers it)")
    return _store[0]


async def screen_and_store(tenant_id: UUID, content: bytes, file_name: str) -> StoredFile:
    """Scan, type and store one file; a refused file raises the evidence upload's refusal."""
    screen, _ = _registered()
    return await screen(tenant_id, content, file_name)


async def read_stored(
    tenant_id: UUID, key: str, version_id: str, sha256: str, size_bytes: int
) -> bytes:
    """A stored file's verified bytes, for a caller that authorised its own action."""
    _, read = _registered()
    return await read(tenant_id, key, version_id, sha256, size_bytes)
