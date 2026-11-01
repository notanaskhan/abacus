# portal

Zone: amber. Pre-registered by F-03-T08 (ADR-140); empty until its first epic.

Will own (docs/plan/03-backend-architecture.md §2.2): Portal branding, domains and preferences. Owns no business truth: a client-facing BFF over other modules' api.py.

Read models (C5 section `portal-pbc`): `documents.py` (POR-03, POR-04; R-01-T07) and `rooms.py`
(POR-14, the third-party room; R-01-T13, DEC-387). `notices.py` tells a request's firm owner of a
third party's upload (`third_party.uploaded`).

Home (POR-02, P-08-T13): `GET /v1/portal/home` and `PUT /v1/portal/preferences` behind `portal.home_v2`; branding and the host (`GET /v1/portal/branding`, public, cached a minute per host).

Rollout (P-08-T28; DEC-456): `portal.home_v2` is on for every synthetic firm the seeds build and for the production canary by hand; it and the legacy `ClientHome` path retire together in one PR after the canary walk (TASK-1359's checklist). Sign-in incidents: RB-35 (a locked-out client) and RB-36 (pause a firm's portal sign-in).

## T-02's portal surfaces (closed 2026-11-01)

POR-05 (Questions) mounts at `/questions` and POR-13 (My K-1s) at `/k1s`. A K-1-only person (a
recipient with no other grant) gets the reduced `k1` shell (DEC-129): My K-1s alone, no Documents
or Messages. The portal never renders the product's name (INV-4).

