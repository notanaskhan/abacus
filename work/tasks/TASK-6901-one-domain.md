---
id: TASK-6901
title: One registered domain for the firm app, the portal and mail (F-09-T09)
spec: SPEC-049  # row F-09-T09 (AC-8, AC-11)
acceptance_criteria: [AC-8, AC-11]
risk_zone: amber
status: done
branch: f09-t09-one-domain
created: 2026-11-10
updated: 2026-11-10
---

## Objective
Ayush registered one domain and chose it for every role, the firm app too (DEC-3901). Make the
repo safe for that: no firm can take a platform host, Terraform makes one zone, and the
documents that waited on F-09-T09 name the hosts.

## Scope
**In**
- `portal/branding.py`: `RESERVED_LABELS` and `reserved_host`; `add_portal_host` refuses the
  domain itself and a reserved label one level under it.
- `infra/envs/shared/zones.tf`, `outputs.tf`: one zone when `firm_domain` = `portal_base_domain`.
- Intuit draft (host rows, redirect URI path from code, DR row), the cutover runbook's redirect
  path, the vendor tracker, `infra/README.md` step 8, the row's status (partial), DEC-3901.

**Out**
- The domain name in the repo (public; vault and untracked tfvars only).
- Applying Terraform, delegating DNS, the registrar's MFA and lock (Ayush).
- The connect-host hand-off (A-02-T33), the firm edge's alias, SES identities (Q-01).

## Plan
- [x] Plan approved by human (Ayush, 2026-11-10: "Everything, firm app too")

1. [x] Reserved labels: admin, api, app, auth, autodiscover, bounce, connect, docs, help, mail,
   mta-sts, notify, portal, staging, status, support, www. Checked only directly under
   `portal_base_domain`; custom firm domains are outside it.
2. [x] Terraform: the portal zone's count is 0 when the two domains are equal; the `portal`
   name-server output falls back to the firm zone.
3. [x] Tests: `tests/unit/portal/test_reserved_hosts.py`.

Rollback: revert the commit. No migration, no flag; the zone change plans to nothing while both
variables are null.

## Progress log
- 2026-11-10: built; 13 unit tests pass; `terraform fmt -check` clean. Found the code's redirect
  path is `/client/connect/callback` (not the `/v1/connections/callback` the runbook and draft
  had), and that the callback page needs a session the connect host cannot have. Recorded as
  open for A-02-T33 rather than fixed here.
- 2026-11-10: applied `shared` from this branch (one zone added, nothing else). The state lock
  write needed KMS backend flags (infra/README step 8). Until this merges, a `shared` apply from
  a checkout without both domain variables would plan to destroy the zone.
- 2026-11-10: Ayush set the four Route 53 name servers at the registrar; the .si registry
  published them at 10:03 UTC (Cloudflare and Quad9 resolve them; Google still cached the parking
  answer). Row stays partial until Ayush confirms registrar MFA.
- 2026-11-10: Ayush waived registrar MFA ("Skip MFA, not required"; admin override, DEC-3903).
  F-09-T09 marked done.
