# portal

Zone: amber. Pre-registered by F-03-T08 (ADR-140); empty until its first epic.

Will own (docs/plan/03-backend-architecture.md §2.2): Portal branding, domains and preferences. Owns no business truth: a client-facing BFF over other modules' api.py.

Read models (C5 section `portal-pbc`): `documents.py` (POR-03, POR-04; R-01-T07) and `rooms.py`
(POR-14, the third-party room; R-01-T13, DEC-387). `notices.py` tells a request's firm owner of a
third party's upload (`third_party.uploaded`).
