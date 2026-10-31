"""The tax part of the home: the Earlier rows for filed returns (T-01-T41; T-01 §3.14; POR-02).

One row "<year> Form <form> filed and accepted" per return the firm released to the client
(`tax.api.filed_returns`), among the work items `home.py` already authorised for this scope
(`scope_only`, INV-4): another household's return never appears. The row names its release so
the portal can offer the client copy's download; `download_ready` says whether this session has
passed the portal's second step, which the download requires (TRI, P-08's slot).
"""

from __future__ import annotations

from abacus.modules.identity.api import AuthContext
from abacus.modules.portal.home_sources import Earlier, HomePart, HomeScope, register_home_source
from abacus.modules.tax.api import filed_returns


async def tax_filings_source(ctx: AuthContext, scope: HomeScope) -> HomePart:
    part = HomePart()
    returns = [w.id for w in scope.work_items if w.kind == "tax_return"]
    ready = ctx.mfa_at is not None or ctx.portal_second_step
    for filed in await filed_returns(ctx.tenant, returns):
        part.earlier.append(
            Earlier(
                "return_filed",
                filed.delivered_on,
                facts={
                    "tax_year": filed.tax_year,
                    "form": filed.form,
                    "delivery_id": str(filed.delivery_id),
                    "download_ready": ready,
                },
            )
        )
    return part


register_home_source("tax_filings", tax_filings_source)
