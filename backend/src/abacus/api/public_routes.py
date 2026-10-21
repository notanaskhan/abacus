"""The public-route list: the only routes that answer without a token (ADR-152, P-45; Q-01-T16).
PROTECTED.

`AbacusRouter` refuses a route without a matrix action, and an action needs a principal. A load
balancer has none, so its two probes live here, outside the router, and nowhere else may an
unauthenticated route exist. The list is `PUBLIC_ROUTES`; `create_app()` registers exactly those
paths, GET only, out of the OpenAPI document. ROUTE-001 holds the list to the protected exception
list in `abacus_tools.quality.banned_patterns` (`PUBLIC_ROUTE_EXCEPTIONS`), so adding a path is a
deliberate change to a protected file with an ADR behind it. P-08 (`/v1/portal/branding`) and P-01
(`/v1/auth/*`) extend the list through their own proposals.

Bodies are fixed and carry no data: no version, no hostname, no error text. The edge (CloudFront)
answers 403 for both paths; only the load balancer reaches them (Q-01-T15).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Final

from fastapi.responses import JSONResponse

from abacus.kernel.crypto import check_platform_key
from abacus.kernel.db import ping, ping_identity
from abacus.kernel.logging import get_logger
from abacus.kernel.scanning import check_scanner
from abacus.kernel.temporal import ping_temporal

_log = get_logger(__name__)
# Each dependency check gets this long; the load balancer's own timeout is shorter than the sum.
CHECK_TIMEOUT_SECONDS: Final = 3.0
_NO_STORE: Final = {"Cache-Control": "no-store"}

Handler = Callable[[], Awaitable[JSONResponse]]


async def healthz() -> JSONResponse:
    """Process liveness. Calls nothing: a dependency outage must not get the task killed."""
    return JSONResponse({"status": "ok"}, headers=_NO_STORE)


async def _scanner() -> None:
    await asyncio.to_thread(check_scanner)  # a socket round trip, off the event loop


# What readiness means (SPEC-050 AC-24): both database roles, Temporal, the scanner and the
# platform key. A name here is what a failed readiness answer reports.
READINESS_CHECKS: Final[tuple[tuple[str, Callable[[], Awaitable[None]]], ...]] = (
    ("database", ping),
    ("identity_database", ping_identity),
    ("temporal", ping_temporal),
    ("scanner", _scanner),
    ("platform_key", check_platform_key),
)


async def _run(name: str, check: Callable[[], Awaitable[None]]) -> str | None:
    """The check's name if it failed or timed out, else None. The reason is logged by type only:
    a driver or SDK message can carry connection strings or identifiers."""
    try:
        await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
    except Exception as exc:  # any failure, of any kind, means not ready
        _log.warning("readyz.check_failed", check=name, error_type=type(exc).__name__)
        return name
    return None


async def readyz() -> JSONResponse:
    """Ready to take traffic: every dependency answers. 503 names the checks that did not."""
    failed = [
        name for name in await asyncio.gather(*(_run(n, c) for n, c in READINESS_CHECKS)) if name
    ]
    if failed:
        return JSONResponse(
            {"status": "unavailable", "failed": failed}, status_code=503, headers=_NO_STORE
        )
    return JSONResponse({"status": "ready"}, headers=_NO_STORE)


# Path to handler. Keys must stay inside PUBLIC_ROUTE_EXCEPTIONS (ROUTE-001).
PUBLIC_ROUTES: Final[Mapping[str, Handler]] = {
    "/healthz": healthz,
    "/readyz": readyz,
}
