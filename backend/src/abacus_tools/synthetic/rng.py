"""Independent, reproducible random streams (SPEC-001 §6.2).

Each sub-generator draws from its own stream, seeded from sha256("<seed>:<name>"), so adding or
changing one sub-generator never shifts another's output. Nothing here reads the clock, the
environment, the locale or the filesystem.
"""

from __future__ import annotations

import hashlib
import random


def stream(seed: int, name: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{name}".encode()).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))
