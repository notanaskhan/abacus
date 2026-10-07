"""Work classes (ADR-071; SPEC-003): which queue and worker pool work runs on. A leaf module, so
settings, agent specs and the workflow tooling can name a class without importing Temporal."""

from __future__ import annotations

from typing import Final, Literal, get_args

WorkClass = Literal["interactive", "time_sensitive", "background", "batch"]
WORK_CLASSES: Final[tuple[WorkClass, ...]] = get_args(WorkClass)
