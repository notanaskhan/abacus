# Status page content and incident templates (Q-01-T42)

The status page lives at `status.<product-domain>` on Better Stack (P-67; Q-01-T41 sets it up). It is **firm-facing only**: the SHL-05 support drawer's "System status" tab and staff link to it; the client portal never does, because the portal is white-labelled (DEC-01, ADR-133). Runbooks say which template to post (`docs/runbooks/`).

Rules for every word below:

1. **No firm, no client, no person.** Templates and updates never name a firm, a client, a person or a count that could identify one ("one firm in Ohio" identifies). Write about the service, not who was affected. A firm that was affected hears from us directly (RB-27), not from the status page.
2. **No cause that exposes a control** (no host names, vendors' internal names, versions or "attacker").
3. **Status words are the canonical ones** (blueprint §3.3.1, SHL-05): a component is `Operational` or `Needs attention` (the canonical Degraded state). An outage is `Needs attention` with the update saying what does not work. Planned work uses the page's maintenance state, shown as `Maintenance`.
4. **Times are US Central** with the zone written out (`8:40 AM CT`), as the support drawer shows them.
5. **Catalogue honesty:** a component is listed only once its service exists in production.

## Components

From the SHL-05 "System status" list, in its order. Only the first three exist at R1; the others are added by the epic that ships them.

| Component (SHL-05 name) | Listed from | What it covers | Checks behind it |
|---|---|---|---|
| Accrued app | R1 (Q-01-T41) | The firm app: sign-in, requests, evidence, uploads, review | Uptime check on the firm host; SLO-01; the canary (SLO-10) |
| Agents & Workbench | R1 (Q-01-T41) | Agent runs and the workbench | SLO-04, SLO-05 |
| Client portal | R1 (Q-01-T41) | The portal service, described without the firm's brand | Uptime check on the neutral portal host |
| E-signature & identity verification | when its provider is live (R-05) | Signing and identity checks | Provider health |
| CCH Axcess Tax export | when the export is live (A-02, tax) | The tax export | Connector health (`Needs attention` on Degraded) |
| QuickBooks Online sync | when the connector is live (A-02) | Ledger sync | SLO-08, SLO-09 |
| Microsoft 365 mail ingest | when the inbound mailbox is live (N-03) | Inbound client mail | Ingest health |

Below the components: the "Incident history" link and the line "Your firm's data region: US" (SHL-05e), which is true for every firm (R-35).

## Templates

Each template has four updates; post the first within 15 minutes of declaring the incident. Copy, fill the bracketed times and components, and never add a name.

### SEV1: a service is unavailable

**Investigating.** "[Component] is unavailable. We are investigating and will update this page by [time] CT."

**Identified.** "We have found the cause of the [component] outage and are restoring service. Work saved before [time] CT is safe. Next update by [time] CT."

**Monitoring.** "[Component] is working again. We are watching it closely. If something still does not work for you, contact support from the help menu."

**Resolved.** "[Component] has worked normally since [time] CT. We will publish a summary of what happened and what we are changing within five business days."

### SEV2: a service is degraded

**Investigating.** "Some [component] actions are slow or failing. We are investigating and will update this page by [time] CT."

**Identified.** "We have found why [component] is degraded and are fixing it. [Uploads | agent runs | email] may be delayed; nothing is lost. Next update by [time] CT."

**Monitoring.** "[Component] is back to normal speed. We are watching it closely."

**Resolved.** "[Component] has worked normally since [time] CT."

### Planned maintenance

**Scheduled** (post at least three business days ahead; never in a deadline week). "We will carry out planned maintenance on [component] on [date] from [start] to [end] CT. During this window [what will not work]. Everything else keeps working."

**In progress.** "Planned maintenance on [component] has started and is expected to finish by [end] CT."

**Completed.** "Planned maintenance on [component] is complete."

## Portal maintenance banner wording

The portal's branding has a maintenance banner slot (P-08; glossary "Portal branding"), set per firm as data, never in code. The portal never shows the product name and the banner names no firm or client either: the firm's own branding around it already says whose portal it is. Suggested wording for the firm to enter, or for an operator to set through the firm's branding when the platform schedules the work:

<!-- portal-banner:start -->
- Scheduled: "Scheduled maintenance on [date], [start] to [end] CT. You may not be able to sign in or upload during this time."
- Under way: "Maintenance is under way and should finish by [end] CT. Your documents are safe; please try again then."
- Unplanned: "Some features are unavailable at the moment. Your documents are safe; please try again shortly."
<!-- portal-banner:end -->

## Before loading them

The builder reviews this file, then loads the components and the templates into Better Stack by hand (vendor console; record the date in `docs/ops/on-call.md` when Q-01-T41 creates it). Changes to the wording go through this file first.
