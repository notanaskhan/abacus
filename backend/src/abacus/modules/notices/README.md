# notices

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Will own (docs/plan/03-backend-architecture.md §2.2): Tax notices: intakes, analyses and responses.

## Today (F-03-T22, migration 0089)
- **Table:** `notices`, the `notice` work-item subtype: one row per work item, with `notice_code` and `received_on`. Insert-only for the app; the columns it may insert are in `registry.py`.
- **Kind:** `api.py` registers `notice` with engagements' work-item kind slot (`NoticeKind` in `kind.py`). Create one with `engagements.api.create_work_item(ctx, engagement_id, "notice", name=..., details={"notice_code": ..., "received_on": ...})`.
- **Routes:** none (`ROUTERS = ()`).
