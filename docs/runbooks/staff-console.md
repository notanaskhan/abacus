---
id: RB-95
title: "Staff console operations (PLT-01): access, provisioning, entitlements, publications"
owner: builder
alarms: []  # console alarms are G-04 follow-ups; WAF metrics `abacus-<env>-console-ip-allowlist` are the signal
last_rehearsed: never
rehearse_by: 2028-11-07
---
# RB-95 · Staff console operations

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (a staff member cannot reach the console) to SEV1 (the console reachable from outside the allowlist, or a staff identity without MFA) |
| Source | G-04-T22 (TASK-8759); G-04 §3; SPEC-681; DEC-22 / P-54 (ADR-129); `infra/envs/<env>/console_edge.tf`, `infra/modules/waf` (`allow_ipv4_cidrs`) |

## Access
- **Where:** `console.<domain>`, a CloudFront distribution serving `console.html` (the console build, `vite build --mode console`) with its own WebACL.
- **Who:** Accrued staff on the staff issuer (WorkOS, separate from firm users), MFA required; the BFF refuses a session without it.
- **From where:** only the IPv4 CIDRs in the untracked `terraform.tfvars` (`console_allow_ipv4_cidrs`). Any other source gets a WAF block before any other rule.

### Change the allowlist
1. Ticket with the CIDR, whose network it is and until when.
2. Edit `console_allow_ipv4_cidrs` in the environment's untracked tfvars (never commit a CIDR; the repo is public), plan, check only `aws_wafv2_ip_set.allow` changes, apply by hand.
3. Verify from inside and outside the range: inside reaches the sign-in page; outside is blocked (403 from the edge).
4. Rollback: restore the previous tfvars and apply.

### A staff member is locked out
Off-network: connect to an allowlisted network; do not add a home IP for a one-off. MFA lost: reset through the staff issuer's admin, never by disabling MFA for the console.

## Provisioning and entitlements (PLT-01 b, c, g)
- Provision tenant… runs `TenantProvisioningWorkflow` from the signed order form: region, modules, seats, first admins. The toast "Tenant created · invites sent to 2 first admins" and the tinted row confirm it; `tenant.provisioned` is written to the platform log and the firm's trail naming the staff member.
- Entitlement edits (modules, seats, renewal) take a reason and write an entitlement row (P-28); a firm's Request more (ADM-14 f) reaches the console as "Sent to Accrued" and is applied the same way. No price appears anywhere.
- Never: "View as firm", opening client data, or a client's name in the console.

## Publications (two-person)
Help-article sets and reference sets publish from the Publications queue: the drafter cannot approve their own draft; nothing deploys. A wrong publication is superseded by a new one, never edited in place.

## Rollback of the console as a whole
Turn `platform.console` off: the staff routes answer 404 and the console shows its flag-off state; CLI procedures (Q-04) still work. The edge stays up; remove the distribution only through Terraform.

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
| — | staging | — | not yet rehearsed: needs the console host, its certificate and the staff issuer on staging (G-04-T14 rest) |
