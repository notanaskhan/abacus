"""Running a parser on hostile content in a short-lived child process (ADR-110; TASK-052 D2,
TASK-054 D2).

`run_isolated(fn, *args)` runs `fn(*args)` in a freshly spawned process with CPU and memory
limits and a wall-clock timeout, then returns its result. A crash, a hang or a limit hit raises
`IsolationFailed`; an exception `fn` raises on purpose comes back as itself. `fn` and its
arguments and result must be picklable (module-level functions, plain data).
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from concurrent.futures.process import BrokenProcessPool
from contextlib import suppress
from dataclasses import dataclass
from multiprocessing import get_context
from typing import Final

TIMEOUT_SECONDS: Final = 30
CPU_SECONDS: Final = 20
MEMORY_BYTES: Final = 1024 * 1024 * 1024


@dataclass(frozen=True)
class Limits:
    """A child's limits (TASK-069 D3): general ledger parses get more than uploads do."""

    timeout_seconds: int = TIMEOUT_SECONDS
    cpu_seconds: int = CPU_SECONDS
    memory_bytes: int = MEMORY_BYTES


DEFAULT_LIMITS: Final = Limits()


class IsolationFailed(Exception):
    """The child crashed, ran out of time or memory, or couldn't start."""


def _limit(cpu_seconds: int, memory_bytes: int) -> None:
    """In the child: CPU and memory limits (best effort where the platform ignores one)."""
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    # macOS doesn't enforce RLIMIT_AS; the wall-clock timeout still applies there.
    with suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))


def run_isolated[**P, T](
    fn: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """`fn(*args)` in a spawned child with the module's limits."""
    return run_isolated_with(DEFAULT_LIMITS, fn, *args, **kwargs)


def run_isolated_with[**P, T](
    limits: Limits,
    fn: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """`fn(*args)` in a spawned child with these limits."""
    with ProcessPoolExecutor(
        max_workers=1,
        mp_context=get_context("spawn"),
        initializer=_limit,
        initargs=(limits.cpu_seconds, limits.memory_bytes),
    ) as pool:
        future = pool.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=limits.timeout_seconds)
        except (FuturesTimeout, BrokenProcessPool, MemoryError):
            for process in list(pool._processes.values()):  # stop a runaway child now
                process.kill()
            raise IsolationFailed from None


__all__ = [
    "CPU_SECONDS",
    "DEFAULT_LIMITS",
    "MEMORY_BYTES",
    "TIMEOUT_SECONDS",
    "IsolationFailed",
    "Limits",
    "run_isolated",
    "run_isolated_with",
]
