# notices

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Will own (docs/plan/03-backend-architecture.md §2.2): Tax notices: intakes, analyses and responses.

## Notices v1 (N-04)
- **Migration 0650** (N-04-T03, DEC-2052): the v1 columns on `notices`, `notice_intakes`, `notice_responses` and nine insert-only records (`notice_rows_immutable`). Table grants are in `registry.py`.
- **Contract** (N-04-T02, DEC-2051): `contract.py`, `docs/contracts/notices.md`; routes 404 with `notices.workspace` off and 501 until N-04-T06.
- **Red files** (DEC-2050): `compute/notice_types.yaml` and `compute/rate_schedules/*.yaml`.

## Before v1 (F-03-T22, migration 0089)
- **Table:** `notices`, the `notice` work-item subtype: one row per work item, with `notice_code` and `received_on`. Insert-only for the app; the columns it may insert are in `registry.py`.
- **Kind:** `api.py` registers `notice` with engagements' work-item kind slot (`NoticeKind` in `kind.py`). Create one with `engagements.api.create_work_item(ctx, engagement_id, "notice", name=..., details={"notice_code": ..., "received_on": ...})`.
- **Routes:** none (`ROUTERS = ()`).
