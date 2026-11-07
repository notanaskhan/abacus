"""The notices part of the home: POR-02's info row (N-04-T22; N-04 US-8.3, INV-4).

One row per notice the firm has made visible to the client, among the work items `home.py` already
authorised for this scope. The row carries the agency, the tax year and a client code; it never
carries an amount, the analysis or a note. Portal principals reach no `/v1/notices*` route: this
row is all they get of a notice.
"""

from __future__ import annotations

from typing import cast

from abacus.modules.identity.api import AuthContext
from abacus.modules.notices.api import portal_notice_rows
from abacus.modules.portal.codes import NoticeCode
from abacus.modules.portal.home_sources import (
    HomePart,
    HomeScope,
    NoticeInfo,
    register_home_source,
)


async def notices_source(ctx: AuthContext, scope: HomeScope) -> HomePart:
    part = HomePart()
    ids = [w.id for w in scope.work_items if w.kind == "notice"]
    for row in await portal_notice_rows(ctx.tenant, ids):
        part.notices.append(NoticeInfo(row.notice_id, cast(NoticeCode, row.code), row.subject))
    return part


register_home_source("notices", notices_source)
