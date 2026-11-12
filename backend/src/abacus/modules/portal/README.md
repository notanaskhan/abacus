# portal

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Owns portal branding, hosts, settings and preferences (docs/plan/03-backend-architecture.md §2.2). Owns no business truth: a client-facing BFF over other modules' api.py. The portal never renders the product's name (INV-4, DEC-59).

Read models (C5 section `portal-pbc`): `documents.py` (POR-03, POR-04; R-01-T07) and `rooms.py`
(POR-14, the third-party room; R-01-T13, DEC-387). `notices.py` tells a request's firm owner of a
third party's upload (`third_party.uploaded`).

Home (POR-02, P-08-T13): `GET /v1/portal/home` and `PUT /v1/portal/preferences` behind `portal.home_v2`; branding and the host (`GET /v1/portal/branding`, public, cached a minute per host).

Rollout (P-08-T28; DEC-456): `portal.home_v2` is on for every synthetic firm the seeds build and for the production canary by hand; it and the legacy `ClientHome` path retire together in one PR after the canary walk (TASK-1359's checklist). Sign-in incidents: RB-35 (a locked-out client) and RB-36 (pause a firm's portal sign-in).

## T-02's portal surfaces (closed 2026-11-01)

POR-05 (Questions) mounts at `/questions` and POR-13 (My K-1s) at `/k1s`. A K-1-only person (a
recipient with no other grant) gets the reduced `k1` shell (DEC-129): My K-1s alone, no Documents
or Messages. The portal never renders the product's name (INV-4).


## R-01: documents, drops, the room and portal settings (closed 2026-11-12, R-01-T36)
Contracts: C5 section `portal-pbc` (`docs/contracts/portal-pbc.md`, frozen v1), C16 v1.1
(`email-templates.md`, frozen) and `portal-settings.md`. Flip plan and rollback per flag:
`docs/runbooks/r01-portal-flip.md`.
- **Documents** (`documents.py`, POR-03 and POR-04): binders, categories and request items in the
  client's words, scoped to the principal's grants (`scope_only`); the ignore note and undo are
  requests' (R-01-T08). Served to every firm since `portal.documents_v2` retired (DEC-510).
- **Drops** are evidence's (`evidence/drops.py`, behind `portal.drop_sort`): a file dropped on a
  binder goes through the one upload policy, then code may link it to the one request it decisively
  matches among those the dropper can see; otherwise it waits for the firm. A suggestion a person
  accepts (ADR-005). Failures: RB-43 "Portal drops that do not sort".
- **Third-party room** (`rooms.py`, POR-14, behind `portal.third_party_room`): a delegate sees only
  the requests delegated to them, by band, with n of N; invitations follow the delegation
  (DEC-387, DEC-388).
- **Settings and preview** (`settings.py`, ADM-10, behind `portal.settings_editor`): one draft per
  firm (brand slots, client-experience toggles, the follow-up policy) at `expected_version`;
  publish with a fresh second factor applies the brand through P-08's `set_branding`. The preview
  (`?as=`) shows a real contact only within the viewer's `visible()` (communications'
  `preview_scope.py`, DEC-379); it never widens access.
