# G-04 rollout and close-out (G-04-T22, TASK-8759, 2026-11-20)

## Console host and allowlist
- Terraform: `infra/modules/waf` gains `allow_ipv4_cidrs` (an IP set and a priority-4 block rule for every other source; off when empty); `infra/modules/cloudfront-firm` gains `default_root_object`; `infra/envs/staging/console_edge.tf` builds the console WebACL and distribution once `console_host`, `console_certificate_arn` and `console_allow_ipv4_cidrs` are set in the untracked tfvars; the web bucket lets the console distribution read through OAC. `terraform validate` passes; offline tests `infra/tests/test_console_edge.py`.
- **Not done (the builder's, by hand):** the console domain and certificate, the CIDR list, `terraform apply`, deploying `dist/console` to the web bucket, and the check that the console is reachable only from the allowlist with staff SSO and MFA on staging.

## Security review (self-review, red)
- [x] No CIDR, host or certificate committed (public repo); tfvars stay untracked.
- [x] The allowlist rule blocks before managed rules; the WebACL's default action is the only allow.
- [x] The console build carries the same CSP as the firm app (G-04-T14); staff sign-in is the staff issuer with MFA (DEC-22, ADR-129).
- [x] No console state approves a support session; the emergency-approve route is gone (SPEC-681 AC-15; e2e PLT-01d).
- [ ] Staff BFF session lifetime and MFA freshness on staging: needs the staging staff issuer.

## Nov 2028 delta pen-test scope
Deferred with every penetration test (DEC-1389): recorded as deferred, never as met. Scope when it runs: the console host and its WAF allowlist bypass attempts; the staff BFF (session fixation, MFA bypass, CSRF); the staff routes (`platform.console`) for cross-tenant reads; support-session request and approval paths (no staff approve; firm approval only); `/v1/firm/plan`, budget alerts and plan requests (`platform.plan_usage`); SHL-05 chat, help and status routes (`support.panel_v2`) for injection and cross-firm reads.

## Flag renewal ticket
`platform.console`, `platform.plan_usage`, `support.panel_v2` (`docs/architecture/feature-flags/platform.yaml`, expire 2027-05-13 in the repo's calendar; the plan's dates are the 2028 train: renew Thu Nov 2 to Dec 19, retire by Tue Dec 19).
- **Change:** extend `expires` once, in the protected flags bundle, in a merge train outside a mini-freeze.
- **Rollback:** revert the bundle PR; an expired flag reads off (ADR-089), so the safe direction is off.

## Flips
1. **Canary (plan: Tue Nov 7, 19:00 CT):** `platform.plan_usage` and `support.panel_v2` on for the canary tenant; `platform.console` on globally for staff once the edge is applied. Smoke: ADM-14 a, SHL-05 a/e, PLT-01 a.
   **Rollback:** turn the flag off for the canary tenant (ADM-14 and SHL-05 go to their flag-off states; P-01's interim Support frame returns); `platform.console` off returns staff to the Q-04 CLI procedures.
2. **Firms (plan: from Tue Nov 14, Tuesdays 19:00 CT):** per firm, `platform.plan_usage` then `support.panel_v2`, both founders' approvals recorded by name. Real pilot firms: none yet (DEC-1391); PF-X1 runs it synthetically (DEC-1530).
   **Rollback:** per firm, flags off in reverse order; nothing is deleted.

## Runbooks
RB-12 (firm-content support sessions after G-04), RB-95 staff console, RB-96 support panel and status. Q-04's provisioning and `make entitlement` procedures stay as the fallback while `platform.console` is off.

## Capacity ledger
G-04-T22: 0.5 planned (N); built in AY's solo session (AMENDMENT-solo). G-04 total 19.25 task-equivalents as planned; S51 share 0.5 / 1.
